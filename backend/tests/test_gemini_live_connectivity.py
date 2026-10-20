"""Live Gemini API connectivity tests.

WARNING: These tests make REAL API calls and consume quota.
Run ONLY with explicit approval and use SPARINGLY.

Test budget: Maximum 2 real API requests total.
"""
import pytest
import os
from pathlib import Path

from app.services.extraction.gemini_adapter import GeminiExtractor
from app.services.extraction.gemini_key_manager import get_key_manager
from app.services.extraction.quota_manager import get_quota_manager


# Mark all tests in this module as requiring explicit approval
pytestmark = pytest.mark.skip(reason="Live API tests disabled by default. Enable with --run-live flag.")


@pytest.fixture(scope="module")
def check_prerequisites():
    """Verify prerequisites before running live tests."""
    # Check environment
    demo_mode = os.getenv("DEMO_MODE", "true").lower() == "true"
    if demo_mode:
        pytest.skip("DEMO_MODE=true, cannot run live API tests")
    
    # Check API keys
    key_manager = get_key_manager()
    if key_manager.get_total_key_count() == 0:
        pytest.skip("No API keys configured")
    
    # Check model
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    if "exp" in model or "2.0" in model:
        pytest.skip(f"Model {model} may be deprecated, update GEMINI_MODEL")
    
    # Check quota
    quota_manager = get_quota_manager()
    can_proceed, quota_status = quota_manager.check_quota_available(model)
    if not can_proceed:
        pytest.skip(f"Quota exhausted: {quota_status.error_message}")
    
    return {
        "model": model,
        "key_count": key_manager.get_total_key_count(),
    }


@pytest.fixture
def synthetic_test_image():
    """Load synthetic test image (NOT real patient data)."""
    # TODO: Create actual synthetic test image
    # For now, return placeholder
    test_image_path = Path(__file__).parent / "fixtures" / "synthetic_form.png"
    
    if not test_image_path.exists():
        pytest.skip("Synthetic test image not found. Create fixtures/synthetic_form.png")
    
    return test_image_path.read_bytes()


class TestGeminiLiveConnectivity:
    """Live API connectivity tests - USE SPARINGLY."""
    
    def test_basic_connectivity(self, check_prerequisites, synthetic_test_image):
        """Test 1/2: Basic Gemini API connectivity and model availability.
        
        COST: 1 API request
        """
        model = check_prerequisites["model"]
        
        # Create extractor
        extractor = GeminiExtractor(model=model, prompt_version="2.0")
        
        # Perform extraction
        result = extractor.extract(
            image=synthetic_test_image,
            document_id="test_live_001",
            page_index=0
        )
        
        # Verify result structure
        assert result is not None
        assert result.schema_version == "1.0"
        assert result.model_id == model
        assert result.prompt_version == "2.0"
        assert result.processing_time_ms > 0
        
        # Verify fields exist
        assert "patient_first_name" in result.fields
        assert "patient_last_name" in result.fields
        assert "patient_id_number" in result.fields
        assert "sender" in result.fields
        assert "received_date" in result.fields
        assert "central_numbers" in result.fields
        assert "commitment_numbers" in result.fields
        
        # Verify field types
        assert isinstance(result.fields["central_numbers"], list)
        assert isinstance(result.fields["commitment_numbers"], list)
        assert isinstance(result.warnings, list)
        
        # Verify quota tracking
        quota_usage = get_quota_manager().get_quota_usage()
        assert quota_usage["requests_today"] >= 1
        
        print(f"\n✅ Live API Test 1 PASSED")
        print(f"   Model: {model}")
        print(f"   Processing time: {result.processing_time_ms:.0f}ms")
        print(f"   Quota used today: {quota_usage['requests_today']}/{quota_usage['daily_limit']}")
    
    def test_structured_output_validation(self, check_prerequisites, synthetic_test_image):
        """Test 2/2: Verify structured output with Pydantic schema.
        
        COST: 1 API request
        """
        model = check_prerequisites["model"]
        
        # Create extractor
        extractor = GeminiExtractor(model=model, prompt_version="2.0")
        
        # Perform extraction
        result = extractor.extract(
            image=synthetic_test_image,
            document_id="test_live_002",
            page_index=0
        )
        
        # Validate field extraction worked
        fields = result.fields
        
        # All required fields must be present (even if null)
        required_fields = {
            'patient_first_name', 'patient_last_name', 'patient_id_number',
            'sender', 'received_date', 'central_numbers', 'commitment_numbers'
        }
        assert required_fields.issubset(fields.keys()), f"Missing fields: {required_fields - fields.keys()}"
        
        # Validate types for nullable fields
        for field in ['patient_first_name', 'patient_last_name', 'patient_id_number', 'sender', 'received_date']:
            value = fields[field]
            assert value is None or isinstance(value, str), f"{field} must be string or null, got {type(value)}"
        
        # Validate types for array fields (never null, can be empty)
        for field in ['central_numbers', 'commitment_numbers']:
            value = fields[field]
            assert isinstance(value, list), f"{field} must be list, got {type(value)}"
            if value:  # If not empty, all items must be strings
                assert all(isinstance(item, str) for item in value), f"{field} must contain only strings"
        
        # Verify JSON response was successfully parsed
        assert result.raw_response is not None
        assert len(result.raw_response) > 0
        
        # Check quota usage
        quota_usage = get_quota_manager().get_quota_usage()
        
        print(f"\n✅ Live API Test 2 PASSED")
        print(f"   Model: {model}")
        print(f"   Fields extracted: {sum(1 for v in fields.values() if v not in [None, []])}")
        print(f"   Warnings: {len(result.warnings)}")
        print(f"   Quota used today: {quota_usage['requests_today']}/{quota_usage['daily_limit']}")
        print(f"   Quota remaining: {quota_usage['daily_remaining']} requests")


class TestQuotaManagement:
    """Test quota management WITHOUT making real API calls."""
    
    def test_quota_tracking_mock(self):
        """Test that quota tracking works (mock, no API calls)."""
        quota_manager = get_quota_manager()
        
        # Get initial usage
        usage_before = quota_manager.get_quota_usage()
        
        # Track a request
        can_proceed, reason = quota_manager.track_request()
        assert can_proceed is True
        assert reason is None
        
        # Verify counter incremented
        usage_after = quota_manager.get_quota_usage()
        assert usage_after["requests_this_minute"] == usage_before["requests_this_minute"] + 1
        assert usage_after["requests_today"] == usage_before["requests_today"] + 1
    
    def test_quota_usage_structure(self):
        """Test quota usage returns expected structure."""
        quota_manager = get_quota_manager()
        usage = quota_manager.get_quota_usage()
        
        # Verify structure
        assert "requests_this_minute" in usage
        assert "requests_today" in usage
        assert "minute_limit" in usage
        assert "daily_limit" in usage
        assert "minute_remaining" in usage
        assert "daily_remaining" in usage
        assert "seconds_until_minute_reset" in usage
        
        # Verify types
        assert isinstance(usage["requests_this_minute"], int)
        assert isinstance(usage["requests_today"], int)
        assert isinstance(usage["minute_limit"], int)
        assert isinstance(usage["daily_limit"], int)
        
        # Verify limits match FREE_TIER_LIMITS
        assert usage["minute_limit"] == 5   # Updated for gemini-3.8-flash
        assert usage["daily_limit"] == 20   # Updated for gemini-3.8-flash


class TestKeyManagerLive:
    """Test key manager WITHOUT making real API calls."""
    
    def test_keys_loaded_from_env(self):
        """Test that keys are loaded from environment."""
        key_manager = get_key_manager()
        
        total = key_manager.get_total_key_count()
        active = key_manager.get_active_key_count()
        
        # At least one key should be loaded
        assert total >= 1, "No API keys found in environment"
        assert active >= 1, "No active API keys"
        
        # Active count should not exceed total
        assert active <= total
        
        print(f"\n📊 Key Manager Status:")
        print(f"   Total keys loaded: {total}")
        print(f"   Active keys: {active}")
    
    def test_key_status_no_exposure(self):
        """Test that key status doesn't expose actual key values."""
        key_manager = get_key_manager()
        status = key_manager.get_status()
        
        for key_info in status:
            # Should have key_id, not key_value
            assert "key_id" in key_info
            assert "key_value" not in key_info
            
            # key_id should be generic like "key_1", "key_2"
            assert key_info["key_id"].startswith("key_")
            
            # Should have metadata
            assert "env_var" in key_info
            assert "is_active" in key_info
            assert "failure_count" in key_info


# Instructions for running live tests
"""
TO RUN LIVE TESTS:

1. Verify prerequisites:
   - DEMO_MODE=false in .env
   - At least one valid GEMINI_API_KEY configured
   - GEMINI_MODEL=gemini-3.8-flash (or other active model)
   - No quota exhaustion

2. Create synthetic test image:
   - Create backend/tests/fixtures/synthetic_form.png
   - Use synthetic data ONLY (no real patient information)

3. Run with explicit flag:
   pytest backend/tests/test_gemini_live_connectivity.py --run-live -v

4. Monitor quota usage:
   - Check logs for quota counters
   - Stop if approaching daily limit

BUDGET: Maximum 2 real API requests per test session.
"""
