"""Test that DEMO_MODE=true prevents all Gemini API calls.

CRITICAL: These tests verify that demo mode is properly enforced.
"""
import pytest
import os
from unittest.mock import patch, MagicMock

from app.core.config import Settings


class TestDemoModeEnforcement:
    """Verify DEMO_MODE blocks all real API calls."""
    
    @patch.dict(os.environ, {"DEMO_MODE": "true", "GEMINI_API_KEY": "test-key"}, clear=False)
    def test_demo_mode_uses_mock_extractor(self):
        """Test that DEMO_MODE=true uses MockExtractor, not Gemini."""
        # Reload settings with DEMO_MODE=true
        settings = Settings()
        
        assert settings.demo_mode is True
        
        # Import extractor factory
        from app.services.extraction.mock_extractor import create_extractor
        
        extractor = create_extractor(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            demo_mode=settings.demo_mode
        )
        
        # Should be MockExtractor, not GeminiExtractor
        from app.services.extraction.mock_extractor import MockExtractor
        assert isinstance(extractor, MockExtractor)
    
    @patch.dict(os.environ, {"DEMO_MODE": "false", "GEMINI_API_KEY": "test-key"}, clear=False)
    def test_live_mode_uses_gemini_extractor(self):
        """Test that DEMO_MODE=false uses real GeminiExtractor."""
        settings = Settings()
        
        assert settings.demo_mode is False
        
        # Import extractor factory
        from app.services.extraction.mock_extractor import create_extractor
        
        extractor = create_extractor(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            demo_mode=settings.demo_mode
        )
        
        # Should be GeminiExtractor
        from app.services.extraction.gemini_adapter import GeminiExtractor
        assert isinstance(extractor, GeminiExtractor)
    
    @patch.dict(os.environ, {"DEMO_MODE": "true"}, clear=False)
    def test_demo_mode_never_creates_genai_client(self):
        """Test that MockExtractor never creates google.genai.Client."""
        from app.services.extraction.mock_extractor import MockExtractor
        
        mock_extractor = MockExtractor()
        
        # MockExtractor should not have a client attribute
        assert not hasattr(mock_extractor, 'client')
        
        # Extract should work without any API calls
        result = mock_extractor.extract(
            image=b"fake-image-bytes",
            document_id="test_demo_001",
            page_index=0
        )
        
        assert result is not None
        assert result.model_id == "mock-extractor-v1"  # Correct default model_id
    
    def test_live_api_tests_are_skipped_by_default(self):
        """Test that live API tests are marked to skip by default."""
        import tests.test_gemini_live_connectivity as live_tests
        
        # Check that module has skip marker
        assert hasattr(live_tests, 'pytestmark')
        marker = live_tests.pytestmark
        
        # Should be marked as skip
        assert marker.name == 'skip'
        assert 'disabled by default' in marker.kwargs.get('reason', '').lower()
    
    @patch.dict(os.environ, {"DEMO_MODE": "true", "GEMINI_API_KEY": "test-key"}, clear=False)
    @patch('app.services.extraction.gemini_adapter.genai')
    def test_no_genai_import_in_demo_mode(self, mock_genai):
        """Test that genai module is not used in demo mode."""
        from app.services.extraction.mock_extractor import create_extractor
        from app.core.config import Settings
        
        settings = Settings()
        extractor = create_extractor(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            demo_mode=True  # Explicit demo mode
        )
        
        # Perform extraction
        result = extractor.extract(
            image=b"test-image",
            document_id="test_001",
            page_index=0
        )
        
        # genai.Client should NEVER be called in demo mode
        mock_genai.Client.assert_not_called()
        
        assert result is not None


class TestQuotaManagerMock:
    """Test quota manager with mock data, no real API."""
    
    def test_track_request_increments(self):
        """Test that track_request increments counters."""
        from app.services.extraction.quota_manager import QuotaManager
        
        manager = QuotaManager()
        
        # Get initial state
        usage_before = manager.get_quota_usage()
        minute_before = usage_before["requests_this_minute"]
        day_before = usage_before["requests_today"]
        
        # Track a request
        can_proceed, reason = manager.track_request()
        
        assert can_proceed is True
        assert reason is None
        
        # Verify increment
        usage_after = manager.get_quota_usage()
        assert usage_after["requests_this_minute"] == minute_before + 1
        assert usage_after["requests_today"] == day_before + 1
    
    def test_quota_limit_enforcement_mock(self):
        """Test that quota limits block requests (mock, no API)."""
        from app.services.extraction.quota_manager import QuotaManager
        
        manager = QuotaManager()
        
        # Consume all minute quota (5 RPM for gemini-3.8-flash)
        for i in range(5):
            can_proceed, reason = manager.track_request()
            assert can_proceed is True, f"Request {i+1}/5 should succeed"
        
        # 6th request should be blocked
        can_proceed, reason = manager.track_request()
        assert can_proceed is False
        assert "Rate limit: 5 RPM" in reason
    
    def test_circuit_breaker_blocks_after_429(self):
        """Test that circuit breaker blocks after quota exhaustion."""
        from app.services.extraction.quota_manager import get_quota_manager
        
        manager = get_quota_manager()
        model = "gemini-3.8-flash"
        
        # Initially available
        can_proceed, status = manager.check_quota_available(model)
        assert can_proceed is True
        
        # Mark as exhausted
        manager.mark_quota_exhausted(
            model=model,
            error_message="429 RESOURCE_EXHAUSTED",
            quota_type="daily_quota",
            key_id="key_1"
        )
        
        # Now blocked
        can_proceed, status = manager.check_quota_available(model)
        assert can_proceed is False
        assert status is not None
        assert status.quota_type == "daily_quota"
        assert "key_1" in str(status.affected_key_id)
