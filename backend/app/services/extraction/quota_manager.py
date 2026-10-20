"""Quota management and circuit breaker for Gemini API.

Prevents wasting quota on exhausted resources and implements
intelligent retry logic based on Google API error responses.

CRITICAL: All API keys from the same Google Cloud project share the same quota.
Do NOT rotate keys from the same project to bypass 429 errors.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from dataclasses import dataclass
from threading import Lock


logger = logging.getLogger(__name__)


# Conservative quota limits for Free Tier (per project, not per key)
# NOTE: These limits vary by model and account standing.
# For gemini-3.8-flash Free Tier (as of Oct 2026): 5 RPM, 20 RPD, 250K TPM
# Always check AI Studio for your project's actual limits: https://aistudio.google.com/
FREE_TIER_LIMITS = {
    "requests_per_minute": 5,    # Free Tier for gemini-3.8-flash
    "requests_per_day": 20,      # Free Tier for gemini-3.8-flash (very limited!)
    "max_batch_requests": 15,    # Stop batch early to preserve quota
}


@dataclass
class QuotaStatus:
    """Status of a quota resource."""
    model: str
    quota_type: str  # "rate_limit" or "daily_quota"
    exhausted_at: datetime
    retry_after: Optional[datetime]  # When quota resets
    retry_info_seconds: Optional[float]  # From Google RetryInfo
    error_message: str
    affected_key_id: Optional[str] = None  # Which key triggered the quota error


class QuotaManager:
    """Manages quota exhaustion state and circuit breaker logic.
    
    IMPORTANT: Assumes all API keys belong to the same Google Cloud project
    and therefore share the same quota pool.
    """
    
    def __init__(self):
        self._lock = Lock()
        self._exhausted_quotas: Dict[str, QuotaStatus] = {}
        self._request_count_today = 0
        self._request_count_minute = 0
        self._minute_window_start = datetime.now(timezone.utc)
        self._day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    def check_quota_available(self, model: str) -> tuple[bool, Optional[QuotaStatus]]:
        """Check if quota is available for a model.
        
        Args:
            model: Model name (e.g., "gemini-2.0-flash-exp")
            
        Returns:
            (is_available, quota_status)
            - is_available: True if can make API call
            - quota_status: QuotaStatus if blocked, None otherwise
        """
        with self._lock:
            if model not in self._exhausted_quotas:
                return True, None
            
            status = self._exhausted_quotas[model]
            
            # Check if retry_after has passed
            if status.retry_after:
                now = datetime.now(timezone.utc)
                if now >= status.retry_after:
                    # Quota should be refreshed
                    logger.info(f"Quota for {model} should be refreshed, clearing block")
                    del self._exhausted_quotas[model]
                    return True, None
            
            # Still blocked
            return False, status
    
    def mark_quota_exhausted(
        self,
        model: str,
        error_message: str,
        retry_info_seconds: Optional[float] = None,
        quota_type: str = "daily_quota",
        key_id: Optional[str] = None
    ):
        """Mark a quota as exhausted.
        
        Args:
            model: Model name
            error_message: Full error message from API
            retry_info_seconds: Seconds to wait from RetryInfo (if available)
            quota_type: "rate_limit" or "daily_quota"
            key_id: Which key triggered the error (for logging only)
        """
        with self._lock:
            exhausted_at = datetime.now(timezone.utc)
            
            # Calculate retry_after
            retry_after = None
            if retry_info_seconds:
                retry_after = exhausted_at + timedelta(seconds=retry_info_seconds)
                logger.warning(
                    f"Quota exhausted for {model} ({quota_type}) via {key_id or 'unknown_key'}. "
                    f"Retry after: {retry_after.isoformat()} "
                    f"(in {retry_info_seconds/3600:.1f} hours)"
                )
            else:
                # No retry info - assume daily quota resets at midnight UTC next day
                if quota_type == "daily_quota":
                    next_midnight = (exhausted_at + timedelta(days=1)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    retry_after = next_midnight
                    logger.warning(
                        f"Daily quota exhausted for {model} via {key_id or 'unknown_key'}. "
                        f"Estimated reset at: {retry_after.isoformat()}"
                    )
                else:
                    # Rate limit - retry after 1 minute
                    retry_after = exhausted_at + timedelta(minutes=1)
                    logger.warning(
                        f"Rate limit hit for {model} via {key_id or 'unknown_key'}. "
                        f"Retry after: {retry_after.isoformat()}"
                    )
            
            status = QuotaStatus(
                model=model,
                quota_type=quota_type,
                exhausted_at=exhausted_at,
                retry_after=retry_after,
                retry_info_seconds=retry_info_seconds,
                error_message=error_message,
                affected_key_id=key_id
            )
            
            self._exhausted_quotas[model] = status
            
            logger.error(
                f"[QUOTA EXHAUSTED] {model} - {quota_type} - "
                f"All processing stopped until {retry_after.isoformat() if retry_after else 'unknown'}"
            )
    
    def clear_quota_block(self, model: str):
        """Manually clear quota block for a model.
        
        Args:
            model: Model name
        """
        with self._lock:
            if model in self._exhausted_quotas:
                del self._exhausted_quotas[model]
                logger.info(f"Manually cleared quota block for {model}")
    
    def get_all_exhausted_quotas(self) -> Dict[str, QuotaStatus]:
        """Get all currently exhausted quotas.
        
        Returns:
            Dictionary of model -> QuotaStatus
        """
        with self._lock:
            return dict(self._exhausted_quotas)
    
    def track_request(self) -> tuple[bool, Optional[str]]:
        """Track an API request and check if within quota limits.
        
        Returns:
            (can_proceed, reason_if_blocked)
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            
            # Reset counters if time window changed
            if (now - self._minute_window_start).total_seconds() >= 60:
                self._minute_window_start = now
                self._request_count_minute = 0
            
            if now.date() != self._day_start.date():
                self._day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                self._request_count_today = 0
            
            # Check limits
            if self._request_count_minute >= FREE_TIER_LIMITS["requests_per_minute"]:
                return False, f"Rate limit: {FREE_TIER_LIMITS['requests_per_minute']} RPM"
            
            if self._request_count_today >= FREE_TIER_LIMITS["requests_per_day"]:
                return False, f"Daily quota: {FREE_TIER_LIMITS['requests_per_day']} requests"
            
            # Increment counters
            self._request_count_minute += 1
            self._request_count_today += 1
            
            return True, None
    
    def get_quota_usage(self) -> dict:
        """Get current quota usage statistics.
        
        Returns:
            Dictionary with usage information
        """
        with self._lock:
            now = datetime.now(timezone.utc)
            seconds_since_minute_start = (now - self._minute_window_start).total_seconds()
            
            return {
                "requests_this_minute": self._request_count_minute,
                "requests_today": self._request_count_today,
                "minute_limit": FREE_TIER_LIMITS["requests_per_minute"],
                "daily_limit": FREE_TIER_LIMITS["requests_per_day"],
                "minute_remaining": FREE_TIER_LIMITS["requests_per_minute"] - self._request_count_minute,
                "daily_remaining": FREE_TIER_LIMITS["requests_per_day"] - self._request_count_today,
                "seconds_until_minute_reset": max(0, 60 - seconds_since_minute_start)
            }


# Global quota manager instance
_quota_manager = QuotaManager()


def get_quota_manager() -> QuotaManager:
    """Get the global quota manager instance."""
    return _quota_manager


def parse_gemini_error(error: Exception) -> tuple[bool, Optional[float], str]:
    """Parse Gemini API error to determine quota exhaustion.
    
    Args:
        error: Exception from Gemini API
        
    Returns:
        (is_quota_exhausted, retry_after_seconds, quota_type)
        - is_quota_exhausted: True if daily quota exhausted (not just rate limit)
        - retry_after_seconds: Seconds from RetryInfo, None if not available
        - quota_type: "daily_quota" or "rate_limit"
    """
    error_str = str(error).lower()
    
    # Check for quota exhaustion indicators
    is_daily_quota = (
        "quota exceeded" in error_str or
        "resource_exhausted" in error_str or
        "free tier" in error_str or
        "free_tier" in error_str or
        "generaterequestsperdayperprojectpermodel" in error_str
    )
    
    # Check for rate limit (different from daily quota)
    is_rate_limit = (
        "rate limit" in error_str or
        "too many requests" in error_str
    ) and not is_daily_quota
    
    # Try to extract retry info
    retry_seconds = None
    try:
        # Look for RetryInfo duration pattern
        if "retryinfo" in error_str or "retry" in error_str:
            # Google API sometimes includes: "retryDelay": "13.5h" or similar
            import re
            # Match patterns like: 13.5h, 3600s, 60m
            time_pattern = r'(\d+(?:\.\d+)?)\s*(h|hour|hours|m|min|minutes|s|sec|seconds)'
            matches = re.findall(time_pattern, error_str)
            
            if matches:
                value, unit = matches[0]
                value = float(value)
                
                if unit in ['h', 'hour', 'hours']:
                    retry_seconds = value * 3600
                elif unit in ['m', 'min', 'minutes']:
                    retry_seconds = value * 60
                elif unit in ['s', 'sec', 'seconds']:
                    retry_seconds = value
    except Exception as e:
        logger.warning(f"Failed to parse retry info: {e}")
    
    if is_daily_quota:
        return True, retry_seconds, "daily_quota"
    elif is_rate_limit:
        return False, retry_seconds, "rate_limit"
    else:
        return False, None, "unknown"
