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


# Local conservative safety budgets, NOT the provider's actual project quotas.
# Actual limits depend on project/model/tier; rotating keys does not increase them.
class _LocalLimits(dict):
    """Defaults below; requests_per_minute/day are read from settings (LOCAL_QUOTA_REQUESTS_PER_MINUTE/DAY) at use time."""

    def __getitem__(self, key):
        from app.core.config import settings
        if key == "requests_per_minute":
            return settings.local_quota_requests_per_minute
        if key == "requests_per_day":
            return settings.local_quota_requests_per_day
        return super().__getitem__(key)


FREE_TIER_LIMITS = _LocalLimits({
    "requests_per_minute": 5,
    "requests_per_day": 20,
    "max_batch_requests": 15,
})


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
        # Skip quota checks in DEMO_MODE (MockExtractor doesn't use API)
        from app.core.config import settings
        if settings.demo_mode:
            return True, None  # Always available in demo mode
        
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
                # No provider RetryInfo: apply conservative local cooldown.
                if quota_type == "daily_quota":
                    # Conservative cooldown, not a claim about the provider reset time.
                    # Gemini daily quotas reset at Pacific midnight, not UTC midnight.
                    retry_after = exhausted_at + timedelta(days=1)
                    logger.warning(
                        f"Daily quota exhausted for {model} via {key_id or 'unknown_key'}. "
                        f"Local cooldown until: {retry_after.isoformat()}"
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
                error_message="Daily quota exhausted" if quota_type == "daily_quota" else "Rate limit reached",
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
        # Skip tracking in DEMO_MODE (MockExtractor doesn't use API)
        from app.core.config import settings
        if settings.demo_mode:
            return True, None  # Always allow in demo mode
        
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
    
    # RESOURCE_EXHAUSTED/429 alone does not distinguish daily, minute or spend limits.
    is_daily_quota = any(term in error_str for term in
                         ("perday", "per day", "daily quota", "daily_quota"))
    is_rate_limit = (getattr(error, "code", None) == 429 or any(term in error_str for term in
                     ("429", "resource_exhausted", "resource exhausted", "rate limit", "too many requests", "quota exceeded"))) and not is_daily_quota

    # Try to extract retry info
    retry_seconds = None
    try:
        # Look for RetryInfo duration pattern
        if "retryinfo" in error_str or "retry" in error_str:
            # Google API sometimes includes: "retryDelay": "13.5h" or similar
            import re
            # Match patterns like: 13.5h, 3600s, 60m
            time_pattern = r'(?:retrydelay[\"\':\s]+|retry(?:\s+after|\s+in)?[\"\':\s]+)(\d+(?:\.\d+)?)\s*(hours?|h|minutes?|min|m|seconds?|sec|s)\b'
            matches = re.findall(time_pattern, error_str)
            
            if matches:
                value, unit = matches[0]
                value = float(value)
                
                if unit in ['h', 'hour', 'hours']:
                    retry_seconds = value * 3600
                elif unit in ['m', 'min', 'minute', 'minutes']:
                    retry_seconds = value * 60
                elif unit in ['s', 'sec', 'second', 'seconds']:
                    retry_seconds = value
    except Exception as e:
        logger.warning(f"Failed to parse retry info: {e}")
    
    if is_daily_quota:
        return True, retry_seconds, "daily_quota"
    elif is_rate_limit:
        return False, retry_seconds, "rate_limit"
    else:
        return False, None, "unknown"
