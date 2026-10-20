"""Tests for classification logic."""
import pytest

from app.domain.models import (
    TestRecord, CommitmentRecord, FieldValue,
    ExtractionState, ReviewState
)
from app.services.classification import classify_record, is_field_missing


def create_valid_record() -> TestRecord:
    """Create a fully valid test record for testing."""
    record = TestRecord(
        test_id="test_valid",
        document_id="doc_001",
        page_indices=[0]
    )
    
    # All required fields present and valid
    record.patient_first_name = FieldValue[str](
        raw_value="יוסי",
        normalized_value="יוסי",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_001"
    )
    
    record.patient_last_name = FieldValue[str](
        raw_value="כהן",
        normalized_value="כהן",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_002"
    )
    
    record.patient_id_number = FieldValue[str](
        raw_value="123456789",
        normalized_value="123456789",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_003"
    )
    
    record.sender = FieldValue[str](
        raw_value="תל השומר",
        normalized_value="תל השומר",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_004"
    )
    
    record.received_date = FieldValue[str](
        raw_value="2024-01-15",
        normalized_value="2024-01-15",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_005"
    )
    
    record.central_numbers = FieldValue[list[str]](
        raw_value=["12345"],
        normalized_value=["12345"],
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_006"
    )
    
    return record


def test_all_valid_classifies_as_success():
    """Test that a record with all required fields and no issues classifies as 'success'."""
    record = create_valid_record()
    
    classification = classify_record(record)
    
    assert classification == 'success', "All valid fields should classify as success (Table 1)"


def test_id_with_warning_classifies_as_warnings():
    """Test that a record with one field having a warning classifies as 'warnings'."""
    record = create_valid_record()
    
    # Make ID uncertain
    record.patient_id_number = FieldValue[str](
        raw_value="12345678?",
        normalized_value="12345678",
        extraction_state=ExtractionState.uncertain,
        review_state=ReviewState.needs_review,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_007"
    )
    
    classification = classify_record(record)
    
    assert classification == 'warnings', "Field with warning should classify as warnings (Table 2)"


def test_missing_last_name_classifies_as_missing():
    """Test that a record with a missing required field classifies as 'missing'."""
    record = create_valid_record()
    
    # Make last_name missing
    record.patient_last_name = FieldValue[str](
        raw_value=None,
        normalized_value=None,
        extraction_state=ExtractionState.missing,
        review_state=ReviewState.needs_review,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_008"
    )
    
    classification = classify_record(record)
    
    assert classification == 'missing', "Missing required field should classify as missing (Table 3)"


def test_both_missing_and_warning_prioritizes_missing():
    """Test that priority goes to 'missing' when both issues exist."""
    record = create_valid_record()
    
    # Missing last_name (priority 1)
    record.patient_last_name = FieldValue[str](
        raw_value=None,
        normalized_value=None,
        extraction_state=ExtractionState.missing,
        review_state=ReviewState.needs_review,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_009"
    )
    
    # Uncertain ID (priority 2)
    record.patient_id_number = FieldValue[str](
        raw_value="12345678?",
        normalized_value="12345678",
        extraction_state=ExtractionState.uncertain,
        review_state=ReviewState.needs_review,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_010"
    )
    
    classification = classify_record(record)
    
    assert classification == 'missing', "Missing should take priority over warnings (Table 3)"


def test_confirmed_empty_field_not_missing():
    """Test that a confirmed empty field (reviewed_value='', human_verified) is not missing."""
    record = create_valid_record()
    
    # Confirm first_name as empty (legitimate case, e.g., single name)
    record.patient_first_name = FieldValue[str](
        raw_value=None,
        normalized_value=None,
        reviewed_value="",  # Confirmed empty
        extraction_state=ExtractionState.missing,
        review_state=ReviewState.human_verified,  # Human confirmed it's OK to be empty
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_011"
    )
    
    # Check if field is considered missing
    is_missing = is_field_missing(record.patient_first_name)
    
    assert is_missing is False, "Confirmed empty field should not be considered missing"
    
    # Classification should not be 'missing' because of this field
    classification = classify_record(record)
    
    assert classification == 'success', "Confirmed empty should not cause 'missing' classification"


def test_invalid_field_classifies_as_missing():
    """Test that an invalid field classifies as 'missing'."""
    record = create_valid_record()
    
    # Invalid ID
    record.patient_id_number = FieldValue[str](
        raw_value="abc",
        normalized_value="abc",
        extraction_state=ExtractionState.invalid,
        review_state=ReviewState.needs_review,
        validation_issues=[{"field_name": "patient_id_number", "severity": "error", "message": "Invalid ID format"}],
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_012"
    )
    
    classification = classify_record(record)
    
    assert classification == 'missing', "Invalid required field should classify as missing (Table 3)"


def test_multiple_central_numbers_with_warning():
    """Test that multiple central numbers with one uncertain classifies as warnings."""
    record = create_valid_record()
    
    # Multiple central numbers, one uncertain
    record.central_numbers = FieldValue[list[str]](
        raw_value=["12345", "67890?"],
        normalized_value=["12345", "67890"],
        extraction_state=ExtractionState.uncertain,  # Mark as uncertain
        review_state=ReviewState.needs_review,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_013"
    )
    
    classification = classify_record(record)
    
    assert classification == 'warnings', "Uncertain central_numbers should classify as warnings (Table 2)"


def test_empty_central_numbers_classifies_as_missing():
    """Test that empty central_numbers (required field) classifies as missing."""
    record = create_valid_record()
    
    # Empty central_numbers list
    record.central_numbers = FieldValue[list[str]](
        raw_value=[],
        normalized_value=[],
        extraction_state=ExtractionState.missing,
        review_state=ReviewState.needs_review,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_014"
    )
    
    classification = classify_record(record)
    
    assert classification == 'missing', "Empty central_numbers should classify as missing (Table 3)"


def test_validation_issues_classify_as_warnings():
    """Test that a field with validation issues classifies as warnings."""
    record = create_valid_record()
    
    # Field found but has validation issues
    record.patient_id_number = FieldValue[str](
        raw_value="12345",  # Too short
        normalized_value="12345",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        validation_issues=[{"field_name": "patient_id_number", "severity": "warning", "message": "ID should be 9 digits"}],
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_015"
    )
    
    classification = classify_record(record)
    
    assert classification == 'warnings', "Validation issues should classify as warnings (Table 2)"
