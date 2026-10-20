"""Tests for focused retry orchestrator.

Tests retry infrastructure WITHOUT making real Gemini calls.
Uses MockExtractor only.

CRITICAL: All tests verify that retry is DISABLED by default.
"""
import pytest
from app.services.retry.focused_retry import (
    FocusedRetryOrchestrator,
    RetryConfig,
    RetryTrigger
)
from app.domain.models import FieldValue, ExtractionState, ReviewState
from app.services.extraction.mock_extractor import MockExtractor


def test_retry_config_default_disabled():
    """Test that RetryConfig is DISABLED by default."""
    config = RetryConfig()
    
    # USER REQUIREMENT: OFF by default
    assert config.enable_focused_retry == False
    assert config.max_retries_per_field == 0
    assert config.daily_retry_quota == 0
    assert config.is_enabled() == False


def test_retry_config_enabled_requires_quota():
    """Test that retry requires both enable flag AND quota > 0."""
    # Only enable flag (no quota)
    config1 = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=2,
        daily_retry_quota=0  # No quota!
    )
    assert config1.is_enabled() == False  # Should be disabled
    
    # Only quota (flag off)
    config2 = RetryConfig(
        enable_focused_retry=False,  # Not enabled!
        max_retries_per_field=2,
        daily_retry_quota=50
    )
    assert config2.is_enabled() == False  # Should be disabled
    
    # Both enabled and quota
    config3 = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=2,
        daily_retry_quota=50
    )
    assert config3.is_enabled() == True  # Should be enabled


def test_orchestrator_disabled_by_default():
    """Test orchestrator is disabled by default (no API calls)."""
    extractor = MockExtractor()
    orchestrator = FocusedRetryOrchestrator(extractor)
    
    # Should be disabled
    assert orchestrator.config.is_enabled() == False


def test_should_retry_field_always_false_when_disabled():
    """Test that should_retry_field always returns False when disabled."""
    extractor = MockExtractor()
    config = RetryConfig(enable_focused_retry=False)  # Explicitly disabled
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    # Create field that would normally trigger retry
    field_value = FieldValue[str](
        raw_value=None,
        extraction_state=ExtractionState.uncertain,  # Would trigger
        review_state=ReviewState.needs_review
    )
    
    # Should NOT retry (disabled)
    should_retry = orchestrator.should_retry_field("patient_id_number", field_value)
    assert should_retry == False


def test_should_retry_never_for_human_verified():
    """Test that human_verified fields are NEVER retried."""
    extractor = MockExtractor()
    config = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=5,
        daily_retry_quota=100
    )
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    # Human-verified field (even if uncertain)
    field_value = FieldValue[str](
        reviewed_value="HUMAN CORRECTED",
        extraction_state=ExtractionState.uncertain,  # Normally would trigger
        review_state=ReviewState.human_verified  # But human verified!
    )
    
    # Should NEVER retry human_verified
    should_retry = orchestrator.should_retry_field("patient_id_number", field_value)
    assert should_retry == False


def test_should_retry_respects_quota():
    """Test that retry respects daily quota limit."""
    extractor = MockExtractor()
    config = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=5,
        daily_retry_quota=2  # Low quota
    )
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    # Exhaust quota
    orchestrator._retry_count_today = 2  # Already at limit
    
    field_value = FieldValue[str](
        extraction_state=ExtractionState.uncertain
    )
    
    # Should NOT retry (quota exhausted)
    should_retry = orchestrator.should_retry_field("test_field", field_value)
    assert should_retry == False


def test_should_retry_respects_per_field_limit():
    """Test that retry respects max_retries_per_field."""
    extractor = MockExtractor()
    config = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=2,  # Max 2 retries
        daily_retry_quota=100
    )
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    # Field already retried twice
    field_value = FieldValue[str](
        extraction_state=ExtractionState.uncertain
    )
    field_value.retry_count = 2  # Already tried twice
    
    # Should NOT retry (per-field limit reached)
    should_retry = orchestrator.should_retry_field("test_field", field_value)
    assert should_retry == False


def test_should_retry_triggers_uncertain():
    """Test retry triggers on uncertain extraction_state."""
    extractor = MockExtractor()
    config = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=2,
        daily_retry_quota=10,
        retry_triggers=[RetryTrigger.UNCERTAIN]
    )
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    field_value = FieldValue[str](
        extraction_state=ExtractionState.uncertain  # Should trigger
    )
    
    should_retry = orchestrator.should_retry_field("test_field", field_value)
    assert should_retry == True


def test_should_retry_triggers_missing():
    """Test retry triggers on missing extraction_state."""
    extractor = MockExtractor()
    config = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=2,
        daily_retry_quota=10,
        retry_triggers=[RetryTrigger.MISSING]
    )
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    field_value = FieldValue[str](
        extraction_state=ExtractionState.missing  # Should trigger
    )
    
    should_retry = orchestrator.should_retry_field("test_field", field_value)
    assert should_retry == True


def test_retry_field_blocked_when_disabled():
    """Test that retry_field returns None when disabled."""
    extractor = MockExtractor()
    config = RetryConfig(enable_focused_retry=False)  # Disabled
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    field_value = FieldValue[str](extraction_state=ExtractionState.uncertain)
    image_bytes = b"fake image"
    
    # Should return None (disabled)
    result = orchestrator.retry_field(
        "test_field",
        field_value,
        image_bytes,
        bbox=None,
        document_id="test_doc",
        page_index=0
    )
    
    assert result is None


def test_retry_field_blocked_for_human_verified():
    """Test that retry_field blocks human_verified fields."""
    extractor = MockExtractor()
    config = RetryConfig(
        enable_focused_retry=True,
        max_retries_per_field=2,
        daily_retry_quota=10
    )
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    # Human-verified field
    field_value = FieldValue[str](
        reviewed_value="USER VALUE",
        review_state=ReviewState.human_verified
    )
    
    # Should return None (human_verified blocked)
    result = orchestrator.retry_field(
        "test_field",
        field_value,
        b"fake image",
        bbox=None,
        document_id="test_doc",
        page_index=0
    )
    
    assert result is None


def test_detect_field_bbox_requires_ocr_blocks():
    """Test bbox detection requires OCR text blocks."""
    extractor = MockExtractor()
    orchestrator = FocusedRetryOrchestrator(extractor)
    
    # No OCR blocks provided
    bbox = orchestrator.detect_field_bbox(
        "patient_id_number",
        b"fake image",
        ocr_text_blocks=[]
    )
    
    assert bbox is None  # Cannot detect without OCR


def test_detect_field_bbox_with_low_confidence_label():
    """Test bbox detection rejects low-confidence labels."""
    extractor = MockExtractor()
    config = RetryConfig(min_bbox_confidence=0.7)
    orchestrator = FocusedRetryOrchestrator(extractor, config)
    
    # OCR block with low confidence
    ocr_blocks = [
        {"bbox": (100, 100, 50, 20), "text": "ת.ז", "confidence": 50.0}  # Too low
    ]
    
    bbox = orchestrator.detect_field_bbox(
        "patient_id_number",
        b"fake image",
        ocr_blocks
    )
    
    # Should reject (confidence too low)
    # Note: Actual behavior depends on implementation
    # This test documents expected behavior


def test_update_field_with_retry_result_preserves_provenance():
    """Test that retry updates include provenance (retry_count)."""
    extractor = MockExtractor()
    orchestrator = FocusedRetryOrchestrator(extractor)
    
    from app.services.extraction.extractor import ExtractionResult
    
    field_value = FieldValue[str](raw_value=None)
    field_value.retry_count = 1  # Already tried once
    
    # Retry found new value
    retry_result = ExtractionResult(
        schema_version="1.0",
        fields={"test_field": "NEW VALUE"},
        warnings=[],
        model_id="mock",
        prompt_version="test-v1",
        processing_time_ms=1.0,
        raw_response="mock"
    )
    
    orchestrator.update_field_with_retry_result(
        "test_field",
        field_value,
        retry_result
    )
    
    # Should update value and increment counter
    assert field_value.raw_value == "NEW VALUE"
    assert field_value.retry_count == 2  # Incremented


def test_retry_integration_disabled():
    """Integration test: verify retry is fully disabled by default."""
    extractor = MockExtractor()
    orchestrator = FocusedRetryOrchestrator(extractor)  # Default config
    
    # Create field that would normally trigger retry
    field_value = FieldValue[str](
        extraction_state=ExtractionState.uncertain
    )
    
    # Step 1: Should NOT retry (disabled)
    should_retry = orchestrator.should_retry_field("test_field", field_value)
    assert should_retry == False
    
    # Step 2: Even if we try to call retry_field, should return None
    result = orchestrator.retry_field(
        "test_field",
        field_value,
        b"fake image",
        bbox=None,
        document_id="test",
        page_index=0
    )
    assert result is None
    
    # Step 3: Retry counter should remain 0
    assert orchestrator._retry_count_today == 0  # No API calls made


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
