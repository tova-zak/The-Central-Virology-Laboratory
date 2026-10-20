"""Gemini API Key Manager with Round-Robin load balancing.

Manages multiple Gemini API keys, detects duplicates, and provides
thread-safe round-robin key selection without exposing sensitive values.
"""
import logging
import os
from typing import List, Optional, Tuple
from dataclasses import dataclass
from threading import Lock
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


@dataclass
class ApiKeyInfo:
    """Information about a single API key."""
    key_id: str  # Internal identifier like "key_1", "key_2"
    key_value: str  # The actual API key (never logged)
    env_var_name: str  # Original environment variable name
    is_active: bool = True  # Whether this key is currently usable
    last_used: Optional[datetime] = None
    failure_count: int = 0


class GeminiKeyManager:
    """Manages multiple Gemini API keys with round-robin selection."""
    
    # Environment variable names for API keys (order matters for fallback)
    KEY_ENV_VARS = [
        "GEMINI_API_KEY",  # Primary key
        "GEMINI_API_1",
        "GEMINI_API_2",
        "GEMINI_API_3",
        "GEMINI_API_4",
        "GEMINI_API_5",
        "GEMINI_API_6",
        "GEMINI_API_7",
        "GEMINI_API_8",
    ]
    
    MAX_FAILURES_BEFORE_DISABLE = 3  # Disable key after N consecutive failures
    
    def __init__(self):
        """Initialize key manager by loading keys from environment."""
        self._lock = Lock()
        self._keys: List[ApiKeyInfo] = []
        self._current_index = 0
        self._load_keys_from_env()
    
    def _load_keys_from_env(self):
        """Load API keys from environment variables."""
        raw_keys = []
        seen_values = set()
        
        for env_var in self.KEY_ENV_VARS:
            key_value = os.getenv(env_var, "").strip()
            
            # Skip empty keys
            if not key_value:
                continue
            
            # Detect duplicates (compare first 10 chars to avoid full key comparison in logs)
            key_prefix = key_value[:min(10, len(key_value))]
            if key_value in seen_values:
                logger.warning(
                    f"Duplicate API key detected in {env_var} (prefix: {key_prefix}...), skipping"
                )
                continue
            
            seen_values.add(key_value)
            raw_keys.append((env_var, key_value))
        
        # Create ApiKeyInfo objects
        for idx, (env_var, key_value) in enumerate(raw_keys, start=1):
            key_info = ApiKeyInfo(
                key_id=f"key_{idx}",
                key_value=key_value,
                env_var_name=env_var,
                is_active=True,
                last_used=None,
                failure_count=0
            )
            self._keys.append(key_info)
        
        if not self._keys:
            logger.error("No valid Gemini API keys found in environment")
            raise ValueError("No Gemini API keys configured")
        
        logger.info(
            f"Loaded {len(self._keys)} unique API key(s): "
            f"{', '.join(k.key_id for k in self._keys)}"
        )
    
    def get_next_key(self) -> Tuple[str, str]:
        """Get the next available API key using round-robin.
        
        Returns:
            (key_id, key_value) tuple
            
        Raises:
            RuntimeError: If no active keys are available
        """
        with self._lock:
            if not self._keys:
                raise RuntimeError("No API keys available")
            
            active_keys = [k for k in self._keys if k.is_active]
            if not active_keys:
                # All keys are disabled - log status and raise
                logger.error(
                    "All API keys are disabled. Status: " +
                    ", ".join(f"{k.key_id}(failures={k.failure_count})" for k in self._keys)
                )
                raise RuntimeError("All API keys are disabled due to repeated failures")
            
            # Round-robin through active keys only
            # Find next active key starting from current index
            attempts = 0
            while attempts < len(self._keys):
                candidate = self._keys[self._current_index % len(self._keys)]
                self._current_index = (self._current_index + 1) % len(self._keys)
                
                if candidate.is_active:
                    candidate.last_used = datetime.now(timezone.utc)
                    logger.debug(f"Selected {candidate.key_id} for API call")
                    return candidate.key_id, candidate.key_value
                
                attempts += 1
            
            # Should never reach here if active_keys is not empty
            raise RuntimeError("Failed to select an active key (logic error)")
    
    def mark_key_failed(self, key_id: str, error_message: str):
        """Mark a key as failed. Disable after MAX_FAILURES_BEFORE_DISABLE.
        
        Args:
            key_id: Internal key identifier (e.g., "key_1")
            error_message: Error message (will NOT be logged with full details)
        """
        with self._lock:
            for key in self._keys:
                if key.key_id == key_id:
                    key.failure_count += 1
                    
                    if key.failure_count >= self.MAX_FAILURES_BEFORE_DISABLE:
                        key.is_active = False
                        logger.error(
                            f"{key_id} disabled after {key.failure_count} consecutive failures. "
                            f"Error type: {type(error_message).__name__}"
                        )
                    else:
                        logger.warning(
                            f"{key_id} failed ({key.failure_count}/{self.MAX_FAILURES_BEFORE_DISABLE}). "
                            f"Error type: {type(error_message).__name__}"
                        )
                    return
            
            logger.warning(f"Attempted to mark unknown key as failed: {key_id}")
    
    def mark_key_success(self, key_id: str):
        """Reset failure count for a key after successful API call.
        
        Args:
            key_id: Internal key identifier (e.g., "key_1")
        """
        with self._lock:
            for key in self._keys:
                if key.key_id == key_id:
                    if key.failure_count > 0:
                        logger.debug(f"{key_id} success, resetting failure count from {key.failure_count}")
                    key.failure_count = 0
                    return
    
    def reactivate_key(self, key_id: str):
        """Manually reactivate a disabled key.
        
        Args:
            key_id: Internal key identifier (e.g., "key_1")
        """
        with self._lock:
            for key in self._keys:
                if key.key_id == key_id:
                    key.is_active = True
                    key.failure_count = 0
                    logger.info(f"Manually reactivated {key_id}")
                    return
            
            logger.warning(f"Attempted to reactivate unknown key: {key_id}")
    
    def get_status(self) -> List[dict]:
        """Get status of all keys (without exposing key values).
        
        Returns:
            List of dictionaries with key status information
        """
        with self._lock:
            return [
                {
                    "key_id": k.key_id,
                    "env_var": k.env_var_name,
                    "is_active": k.is_active,
                    "failure_count": k.failure_count,
                    "last_used": k.last_used.isoformat() if k.last_used else None
                }
                for k in self._keys
            ]
    
    def get_active_key_count(self) -> int:
        """Get number of currently active keys."""
        with self._lock:
            return sum(1 for k in self._keys if k.is_active)
    
    def get_total_key_count(self) -> int:
        """Get total number of loaded keys."""
        return len(self._keys)


# Global key manager instance (lazy-loaded)
_key_manager: Optional[GeminiKeyManager] = None
_key_manager_lock = Lock()


def get_key_manager() -> GeminiKeyManager:
    """Get or create the global key manager instance.
    
    Returns:
        GeminiKeyManager singleton instance
    """
    global _key_manager
    
    if _key_manager is None:
        with _key_manager_lock:
            if _key_manager is None:  # Double-check locking
                _key_manager = GeminiKeyManager()
    
    return _key_manager
