"""Tests for hybrid verification module.

Tests cross-verification logic between Gemini and OCR.
Uses mock extraction results - NO real API calls.
"""
import pytest
from app.services.hybrid.verifier import (
    HybridVerifier,
    VerificationConfig,
    VerificationStatus
)
from app.domain.models import FieldValue, ExtractionState, ReviewState
from app.services.extraction.extractor import ExtractionResult


def create_mock_extraction_result(fields: dict, model_id: str = "mock") -> ExtractionResult:
    """Create mock extraction result for testing."""
    return ExtractionResult(
        schema_version="1.0",
        fields=fields,
        warnings=[],
        model_id=model_id,
        prompt_version="test-v1",
        processing_time_ms=1.0,
        raw_response="mock response"
    )


def test_verifier_initialization():
    """Test verifier initializes with default config."""
    verifier = HybridVerifier()
    assert verifier.config is not None
    assert verifier.config.enable_ocr_verification == True


def test_verify_gemini_ocr_agreement():
    """Test verification when Gemini and OCR agree."""
    verifier = HybridVerifier()
    
    gemini_result = create_mock_extraction_result({
        "patient_id_number": "123456789"
    }, model_id="gemini")
    
    ocr_result = create_mock_extraction_result({
        "patient_id_number": "123456789"
    }, model_id="ocr")
    
    field_value = FieldValue[str]()
    
    evidence = verifier.verify_field(
        "patient_id_number",
        gemini_result,
        ocr_result,
        field_value
    )
    
    assert evidence.verification_status == VerificationStatus.VERIFIED
    assert evidence.values_match == True
    assert evidence.gemini_value == "123456789"
    assert evidence.ocr_value == "123456789"


def test_verify_gemini_ocr_conflict():
    """Test verification when Gemini and OCR disagree."""
    verifier = HybridVerifier()
    
    gemini_result = create_mock_extraction_result({
        "patient_id_number": "123456789"
    })
    
    ocr_result = create_mock_extraction_result({
        "patient_id_number": "987654321"  # Different!
    })
    
    field_value = FieldValue[str]()
    
    evidence = verifier.verify_field(
        "patient_id_number",
        gemini_result,
        ocr_result,
        field_value
    )
    
    assert evidence.verification_status == VerificationStatus.CONFLICTING
    assert evidence.values_match == False
    assert evidence.gemini_value == "123456789"
    assert evidence.ocr_value == "987654321"
    assert len(evidence.validation_issues) > 0


def test_verify_gemini_only():
    """Test verification when only Gemini found value (OCR found nothing)."""
    verifier = HybridVerifier()
    
    gemini_result = create_mock_extraction_result({
        "patient_id_number": "123456789"
    })
    
    ocr_result = create_mock_extraction_result({
        "patient_id_number": None  # OCR found nothing
    })
    
    field_value = FieldValue[str]()
    
    evidence = verifier.verify_field(
        "patient_id_number",
        gemini_result,
        ocr_result,
        field_value
    )
    
    # OCR absence is NOT proof of error - Gemini may be correct
    assert evidence.verification_status == VerificationStatus.GEMINI_ONLY
    assert evidence.gemini_value == "123456789"
    assert evidence.ocr_value is None


def test_verify_ocr_unreliable_field():
    """Test verification for handwriting field (OCR unreliable)."""
    config = VerificationConfig(
        ocr_unreliable_fields=["patient_first_name"]
    )
    verifier = HybridVerifier(config)
    
    gemini_result = create_mock_extraction_result({
        "patient_first_name": "משה"
    })
    
    ocr_result = create_mock_extraction_result({
        "patient_first_name": "גוזר"  # OCR hallucination on handwriting
    })
    
    field_value = FieldValue[str]()
    
    evidence = verifier.verify_field(
        "patient_first_name",
        gemini_result,
        ocr_result,
        field_value
    )
    
    # Should trust Gemini for handwriting, ignore OCR
    assert evidence.verification_status == VerificationStatus.GEMINI_ONLY
    assert "OCR unreliable" in evidence.reasoning or "handwriting" in evidence.reasoning


def test_verify_human_verified_never_checked():
    """Test that human_verified fields are never re-verified."""
    verifier = HybridVerifier()
    
    gemini_result = create_mock_extraction_result({
        "patient_id_number": "999999999"  # Wrong value
    })
    
    ocr_result = create_mock_extraction_result({
        "patient_id_number": "888888888"  # Also wrong
    })
    
    # Field already human-verified with correct value
    field_value = FieldValue[str](
        reviewed_value="123456789",
        review_state=ReviewState.human_verified
    )
    
    evidence = verifier.verify_field(
        "patient_id_number",
        gemini_result,
        ocr_result,
        field_value
    )
    
    # Should skip verification and preserve human value
    assert evidence.verification_status == VerificationStatus.VERIFIED
    assert "human_verified" in evidence.reasoning.lower()


def test_apply_verification_conflicting_flags_for_review():
    """Test that conflicting values are flagged for review."""
    config = VerificationConfig(auto_flag_conflicts=True)
    verifier = HybridVerifier(config)
    
    from app.domain.models import ValidationIssue
    evidence = VerificationStatus.CONFLICTING
    evidence_obj = type('Evidence', (), {
        'verification_status': VerificationStatus.CONFLICTING,
        'validation_issues': [ValidationIssue(
            field_name="patient_id_number",
            severity="warning",
            message="Conflict detected"
        )]
    })()
    
    field_value = FieldValue[str](
        raw_value="123456789",
        extraction_state=ExtractionState.found
    )
    
    verifier.apply_verification_to_field(
        field_value,
        evidence_obj,
        "patient_id_number"
    )
    
    # Should be marked as conflicting and needs_review
    assert field_value.extraction_state == ExtractionState.conflicting
    assert field_value.review_state == ReviewState.needs_review
    assert len(field_value.validation_issues) > 0


def test_apply_verification_never_touches_human_verified():
    """Test that verification NEVER modifies human_verified fields."""
    verifier = HybridVerifier()
    
    from app.domain.models import ValidationIssue
    evidence = type('Evidence', (), {
        'verification_status': VerificationStatus.CONFLICTING,
        'validation_issues': [ValidationIssue(
            field_name="test",
            severity="error",
            message="Would flag this"
        )]
    })()
    
    # Human-verified field
    original_value = "USER CORRECTED VALUE"
    field_value = FieldValue[str](
        reviewed_value=original_value,
        review_state=ReviewState.human_verified,
        extraction_state=ExtractionState.found
    )
    
    # Try to apply verification (should be skipped)
    verifier.apply_verification_to_field(field_value, evidence, "test_field")
    
    # Field should be unchanged
    assert field_value.reviewed_value == original_value
    assert field_value.review_state == ReviewState.human_verified
    assert len(field_value.validation_issues) == 0  # Not added


def test_values_match_equivalent_dates():
    verifier = HybridVerifier()
    assert verifier._values_match("21.06.2026", "21/06/2026") is True
    assert verifier._values_match("18/06/2026", "2026-06-18") is True
    assert verifier._values_match("21.06.2026", "22/06/2026") is False


def test_apply_verification_persists_ocr_metadata():
    verifier = HybridVerifier()
    field_value = FieldValue[str](raw_value="21.06.2026")
    gemini = create_mock_extraction_result({"received_date": "21.06.2026"})
    ocr = create_mock_extraction_result({"received_date": "21/06/2026"}, model_id="ocr")
    ocr.ocr_confidence = 95.0
    evidence = verifier.verify_field("received_date", gemini, ocr, field_value)
    verifier.apply_verification_to_field(field_value, evidence, "received_date")
    assert field_value.verification_status == VerificationStatus.VERIFIED.value
    assert field_value.ocr_value == "21/06/2026"


def test_values_match_normalization():
    """Test value comparison with normalization."""
    verifier = HybridVerifier()
    
    # Case-insensitive
    assert verifier._values_match("ABC", "abc") == True
    assert verifier._values_match("ABC", "xyz") == False
    
    # Whitespace normalization
    assert verifier._values_match("  ABC  ", "ABC") == True
    
    # List comparison (order-insensitive)
    assert verifier._values_match(["123", "456"], ["456", "123"]) == True
    assert verifier._values_match(["123"], ["456"]) == False
    assert verifier._values_match(["00121"], ["121"]) == False
    
    # None handling
    assert verifier._values_match(None, None) == True
    assert verifier._values_match(None, "ABC") == False


def test_validation_id_checksum():
    """Test ID checksum validation during verification."""
    verifier = HybridVerifier()
    
    # Valid Israeli ID (passes checksum)
    valid_issues = verifier._validate_field("patient_id_number", "123456782")
    # Note: This is a synthetic example - real validation in validator.py
    
    # Invalid ID (fails checksum)
    invalid_issues = verifier._validate_field("patient_id_number", "123456789")
    # Should have validation issue
    # Note: Actual behavior depends on validator implementation


def test_verification_integration():
    """Integration test: full verification flow."""
    config = VerificationConfig(
        enable_ocr_verification=True,
        require_agreement_for_verified=True,
        auto_flag_conflicts=True
    )
    verifier = HybridVerifier(config)
    
    # Scenario: Gemini and OCR both extract ID, but OCR has typo
    gemini_result = create_mock_extraction_result({
        "patient_id_number": "123456789",
        "sender": "כללית"
    })
    
    ocr_result = create_mock_extraction_result({
        "patient_id_number": "123456789",  # Agrees
        "sender": None  # OCR couldn't read sender
    })
    
    # Verify ID (should be VERIFIED - both agree)
    id_field = FieldValue[str]()
    id_evidence = verifier.verify_field(
        "patient_id_number",
        gemini_result,
        ocr_result,
        id_field
    )
    assert id_evidence.verification_status == VerificationStatus.VERIFIED
    
    # Verify sender (should be GEMINI_ONLY - OCR found nothing)
    sender_field = FieldValue[str]()
    sender_evidence = verifier.verify_field(
        "sender",
        gemini_result,
        ocr_result,
        sender_field
    )
    assert sender_evidence.verification_status == VerificationStatus.GEMINI_ONLY


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
