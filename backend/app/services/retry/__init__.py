"""Focused retry module for uncertain field re-extraction.

CRITICAL: This module is infrastructure only.
Feature flag MUST be OFF by default.
NO Gemini calls without explicit user approval.
"""

from .focused_retry import FocusedRetryOrchestrator, RetryConfig

__all__ = ["FocusedRetryOrchestrator", "RetryConfig"]
