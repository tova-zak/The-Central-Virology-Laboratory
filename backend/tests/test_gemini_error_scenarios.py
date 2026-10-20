"""Test Gemini error scenarios without real API calls

Tests cover:
1. Successful response
2. HTTP 429 (rate limit)
3. HTTP 404 (model not found)
4. Timeout
5. Parse error
6. QuotaManager blocking

All tests use mocked/fake Gemini client - NO REAL API CALLS
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

import pytest
import time
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, timezone

from app.services.extraction.gemini_adapter import GeminiExtractor, ExtractionError
from app.services.extraction.quota_manager import QuotaStatus


class FakeGeminiResponse:
    """Fake Gemini API response"""
    def __init__(self, text: str):
        self.text = text


class FakeGeminiClient:
    """Fake Gemini client that simulates various scenarios"""
    
    def __init__(self, scenario: str):
        self.scenario = scenario
        self.models = self
    
    def generate_content(self, model, contents, config):
        """Simulate generate_content with different scenarios"""
        if self.scenario == "success":
            # Return valid JSON
            response_json = {
                "patient_first_name": "Test",
                "patient_last_name": "Patient",
                "patient_id_number": "123456789",
                "sender": "כללית",
                "received_date": "15/10/2026",
                "central_numbers": ["12345"],
                "commitment_numbers": ["ABC123"],
                "warnings": []
            }
            return FakeGeminiResponse(json.dumps(response_json))
        
        elif self.scenario == "429":
            # Simulate rate limit error
            raise Exception("429 Resource Exhausted: Quota exceeded for quota metric 'GenerateContent' and limit 'GenerateContent requests per minute per user' of service 'generativelanguage.googleapis.com'")
        
        elif self.scenario == "404":
            # Simulate model not found
            raise Exception("404 Not Found: Model 'gemini-3.8-flash' not found")
        
        elif self.scenario == "timeout":
            # Simulate timeout
            time.sleep(0.1)  # Small delay to simulate network
            raise TimeoutError("Request timed out after 60 seconds")
        
        elif self.scenario == "parse_error":
            # Return invalid JSON
            return FakeGeminiResponse("This is not valid JSON {invalid}")
        
        elif self.scenario == "empty_response":
            # Return empty response
            return FakeGeminiResponse("")
        
        else:
            raise ValueError(f"Unknown scenario: {self.scenario}")


def test_successful_extraction():
    """Test 1: Successful extraction"""
    with patch('app.services.extraction.gemini_adapter.genai.Client') as mock_client_class:
        # Setup mock
        mock_client_class.return_value = FakeGeminiClient("success")
        
        # Create extractor
        extractor = GeminiExtractor(model="gemini-3.8-flash")
        
        # Test extraction
        result = extractor.extract(
            image=b'\x89PNG\r\n\x1a\n' + b'fake_image_data',
            document_id="test_001",
            page_index=0
        )
        
        # Verify
        assert result.model_id == "gemini-3.8-flash"
        assert result.fields['patient_first_name'] == "Test"
        assert result.fields['central_numbers'] == ["12345"]
        assert result.processing_time_ms > 0
        print("✅ Test 1 PASSED: Successful extraction")


def test_rate_limit_429():
    """Test 2: HTTP 429 rate limit"""
    with patch('app.services.extraction.gemini_adapter.genai.Client') as mock_client_class:
        mock_client_class.return_value = FakeGeminiClient("429")
        
        extractor = GeminiExtractor(model="gemini-3.8-flash")
        
        # Should raise ExtractionError (not crash)
        with pytest.raises(ExtractionError) as exc_info:
            extractor.extract(
                image=b'\x89PNG\r\n\x1a\n' + b'fake',
                document_id="test_002",
                page_index=0
            )
        
        # Verify error message mentions quota
        assert "quota" in str(exc_info.value).lower() or "429" in str(exc_info.value)
        print("✅ Test 2 PASSED: 429 handled correctly")


def test_model_not_found_404():
    """Test 3: HTTP 404 model not found"""
    with patch('app.services.extraction.gemini_adapter.genai.Client') as mock_client_class:
        mock_client_class.return_value = FakeGeminiClient("404")
        
        extractor = GeminiExtractor(model="gemini-invalid")
        
        # Should raise ExtractionError
        with pytest.raises(ExtractionError):
            extractor.extract(
                image=b'\x89PNG\r\n\x1a\n' + b'fake',
                document_id="test_003",
                page_index=0
            )
        
        print("✅ Test 3 PASSED: 404 handled correctly")


def test_timeout_error():
    """Test 4: Timeout"""
    # Clear quota state before test
    from app.services.extraction.quota_manager import get_quota_manager
    quota_mgr = get_quota_manager()
    quota_mgr.clear_quota_block("gemini-3.8-flash")
    
    with patch('app.services.extraction.gemini_adapter.genai.Client') as mock_client_class:
        mock_client_class.return_value = FakeGeminiClient("timeout")
        
        extractor = GeminiExtractor(model="gemini-3.8-flash")
        
        # Should raise TimeoutError (not hang forever)
        with pytest.raises((TimeoutError, ExtractionError)) as exc_info:
            extractor.extract(
                image=b'\x89PNG\r\n\x1a\n' + b'fake',
                document_id="test_004",
                page_index=0
            )
        
        # Verify it didn't hang (should return quickly)
        error_msg = str(exc_info.value).lower()
        assert "timeout" in error_msg or "timed out" in error_msg
        print("✅ Test 4 PASSED: Timeout handled correctly")


def test_parse_error():
    """Test 5: JSON parse error"""
    # Clear quota state before test
    from app.services.extraction.quota_manager import get_quota_manager
    quota_mgr = get_quota_manager()
    quota_mgr.clear_quota_block("gemini-3.8-flash")
    
    with patch('app.services.extraction.gemini_adapter.genai.Client') as mock_client_class:
        mock_client_class.return_value = FakeGeminiClient("parse_error")
        
        extractor = GeminiExtractor(model="gemini-3.8-flash")
        
        # Should raise ExtractionError
        with pytest.raises(ExtractionError) as exc_info:
            extractor.extract(
                image=b'\x89PNG\r\n\x1a\n' + b'fake',
                document_id="test_005",
                page_index=0
            )
        
        error_msg = str(exc_info.value).lower()
        assert "json" in error_msg or "parse" in error_msg
        print("✅ Test 5 PASSED: Parse error handled correctly")


def test_quota_manager_blocking():
    """Test 6: QuotaManager blocks request"""
    with patch('app.services.extraction.gemini_adapter.get_quota_manager') as mock_quota:
        # Setup quota manager to block
        mock_quota_instance = Mock()
        mock_quota_instance.check_quota_available.return_value = (
            False, 
            QuotaStatus(
                model="gemini-3.8-flash",
                quota_type="daily_quota",
                exhausted_at=datetime.now(timezone.utc),
                retry_after=datetime.now(timezone.utc) + timedelta(hours=12),
                retry_info_seconds=43200.0,
                error_message="Daily quota exhausted",
                affected_key_id="key_1"
            )
        )
        mock_quota.return_value = mock_quota_instance
        
        extractor = GeminiExtractor(model="gemini-3.8-flash")
        
        # Should raise ExtractionError BEFORE making API call
        with pytest.raises(ExtractionError) as exc_info:
            extractor.extract(
                image=b'\x89PNG\r\n\x1a\n' + b'fake',
                document_id="test_006",
                page_index=0
            )
        
        assert "quota exhausted" in str(exc_info.value).lower()
        print("✅ Test 6 PASSED: QuotaManager blocking works")


def test_no_fallback_to_mock():
    """Test 7: Ensure no fallback to Mock in Live mode"""
    # This test verifies that when GeminiExtractor fails,
    # it does NOT silently fall back to MockExtractor
    
    with patch('app.services.extraction.gemini_adapter.genai.Client') as mock_client_class:
        mock_client_class.return_value = FakeGeminiClient("404")
        
        extractor = GeminiExtractor(model="gemini-invalid")
        
        # Should raise, not return mock data
        with pytest.raises(ExtractionError):
            result = extractor.extract(
                image=b'\x89PNG\r\n\x1a\n' + b'fake',
                document_id="test_007",
                page_index=0
            )
        
        # If we got here, it means no exception was raised (BAD)
        # Check that model_id is NOT mock
        # (But we shouldn't get here if test is correct)
        
        print("✅ Test 7 PASSED: No fallback to Mock")


def test_no_infinite_retry():
    """Test 8: Ensure no infinite retry loop"""
    with patch('app.services.extraction.gemini_adapter.genai.Client') as mock_client_class:
        # Setup client that always fails
        mock_client_class.return_value = FakeGeminiClient("429")
        
        extractor = GeminiExtractor(model="gemini-3.8-flash")
        
        start_time = time.time()
        
        # Should fail quickly (not retry forever)
        with pytest.raises(ExtractionError):
            extractor.extract(
                image=b'\x89PNG\r\n\x1a\n' + b'fake',
                document_id="test_008",
                page_index=0
            )
        
        elapsed = time.time() - start_time
        
        # Should fail in under 5 seconds (not hang for minutes)
        assert elapsed < 5.0, f"Took too long: {elapsed}s (possible retry loop)"
        print(f"✅ Test 8 PASSED: No infinite retry ({elapsed:.2f}s)")


if __name__ == "__main__":
    """Run tests without pytest"""
    print("=" * 80)
    print("GEMINI ERROR SCENARIO TESTS (No Real API Calls)")
    print("=" * 80)
    
    tests = [
        ("Test 1: Successful extraction", test_successful_extraction),
        ("Test 2: HTTP 429 rate limit", test_rate_limit_429),
        ("Test 3: HTTP 404 model not found", test_model_not_found_404),
        ("Test 4: Timeout", test_timeout_error),
        ("Test 5: JSON parse error", test_parse_error),
        ("Test 6: QuotaManager blocking", test_quota_manager_blocking),
        ("Test 7: No fallback to Mock", test_no_fallback_to_mock),
        ("Test 8: No infinite retry", test_no_infinite_retry),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n{name}...")
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)
    
    if failed > 0:
        exit(1)
