"""Test record status calculation for display in סטטוס ביקורת column.

Tests verify that record_status aggregates all fields and relationships:
- לא תקין (validation errors unresolved)
- דורש השלמה (missing required fields)
- דורש בדיקה (warnings/uncertainties unresolved)
- אושר ידנית (all fields human verified)
- תקין (all valid, no issues)
"""
import pytest
from app.domain.models import (
    TestRecord, CommitmentRecord, FieldValue,
    ExtractionState, ReviewState
)
from app.services.classification.classifier import calculate_record_status


def create_base_record() -> TestRecord:
    """Helper to create a base TestRecord with all valid fields."""
    return TestRecord(
        test_id="test_123",
        document_id="doc_001",
        page_indices=[0],
        patient_first_name=FieldValue[str](
            raw_value="ישראל",
            normalized_value="ישראל",
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending
        ),
        patient_last_name=FieldValue[str](
            raw_value="ישראלי",
            normalized_value="ישראלי",
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending
        ),
        patient_id_number=FieldValue[str](
            raw_value="123456789",
            normalized_value="123456789",
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending
        ),
        sender=FieldValue[str](
            raw_value="מכבי",
            normalized_value="מכבי",
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending
        ),
        received_date=FieldValue[str](
            raw_value="2024-01-15",
            normalized_value="2024-01-15",
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending
        ),
        central_numbers=FieldValue[list[str]](
            raw_value=["12345"],
            normalized_value=["12345"],
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending
        )
    )


def test_status_all_valid_returns_תקין():
    """All fields valid with no issues returns תקין."""
    record = create_base_record()
    status = calculate_record_status(record, [])
    assert status == "תקין"


def test_status_validation_error_returns_לא_תקין():
    """Unresolved validation errors return לא תקין."""
    record = create_base_record()
    record.patient_id_number.validation_issues = ["Invalid Israeli ID format"]
    record.patient_id_number.review_state = ReviewState.needs_review
    
    status = calculate_record_status(record, [])
    assert status == "לא תקין"


def test_status_validation_error_resolved_not_לא_תקין():
    """Resolved validation errors (human_verified) don't return לא תקין."""
    record = create_base_record()
    record.patient_id_number.validation_issues = ["Invalid Israeli ID format"]
    record.patient_id_number.review_state = ReviewState.human_verified
    record.patient_id_number.reviewed_value = "123456789"
    
    status = calculate_record_status(record, [])
    assert status != "לא תקין"


def test_status_missing_field_returns_דורש_השלמה():
    """Missing required field returns דורש השלמה."""
    record = create_base_record()
    record.patient_last_name.extraction_state = ExtractionState.missing
    record.patient_last_name.normalized_value = None
    record.patient_last_name.review_state = ReviewState.needs_review
    
    status = calculate_record_status(record, [])
    assert status == "דורש השלמה"


def test_status_uncertain_field_returns_דורש_בדיקה():
    """Uncertain field without resolution returns דורש בדיקה."""
    record = create_base_record()
    record.patient_first_name.extraction_state = ExtractionState.uncertain
    record.patient_first_name.review_state = ReviewState.needs_review
    
    status = calculate_record_status(record, [])
    assert status == "דורש בדיקה"


def test_status_conflicting_field_returns_דורש_בדיקה():
    """Conflicting field without resolution returns דורש בדיקה."""
    record = create_base_record()
    record.patient_id_number.extraction_state = ExtractionState.conflicting
    record.patient_id_number.review_state = ReviewState.needs_review
    
    status = calculate_record_status(record, [])
    assert status == "דורש בדיקה"


def test_status_ambiguous_relationship_returns_דורש_בדיקה():
    """Ambiguous commitment relationship returns דורש בדיקה."""
    record = create_base_record()
    
    commitment = CommitmentRecord(
        commitment_record_id="comm_123",
        test_id=record.test_id,
        commitment_number=FieldValue[str](
            raw_value="98765",
            normalized_value="98765",
            extraction_state=ExtractionState.found
        ),
        central_number_refs=["12345"],
        relation_status="ambiguous"
    )
    
    record.commitment_ids = ["comm_123"]
    
    status = calculate_record_status(record, [commitment])
    assert status == "דורש בדיקה"


def test_status_all_fields_verified_returns_אושר_ידנית():
    """All fields human_verified returns אושר ידנית."""
    record = create_base_record()
    
    # Mark all fields as human_verified
    record.patient_first_name.review_state = ReviewState.human_verified
    record.patient_first_name.reviewed_value = "ישראל"
    
    record.patient_last_name.review_state = ReviewState.human_verified
    record.patient_last_name.reviewed_value = "ישראלי"
    
    record.patient_id_number.review_state = ReviewState.human_verified
    record.patient_id_number.reviewed_value = "123456789"
    
    record.sender.review_state = ReviewState.human_verified
    record.sender.reviewed_value = "מכבי"
    
    record.received_date.review_state = ReviewState.human_verified
    record.received_date.reviewed_value = "2024-01-15"
    
    record.central_numbers.review_state = ReviewState.human_verified
    record.central_numbers.reviewed_value = ["12345"]
    
    status = calculate_record_status(record, [])
    assert status == "אושר ידנית"


def test_status_priority_validation_over_missing():
    """Validation errors have higher priority than missing fields."""
    record = create_base_record()
    
    # Has both validation error and missing field
    record.patient_id_number.validation_issues = ["Invalid format"]
    record.patient_id_number.review_state = ReviewState.needs_review
    
    record.patient_last_name.extraction_state = ExtractionState.missing
    record.patient_last_name.normalized_value = None
    
    status = calculate_record_status(record, [])
    assert status == "לא תקין"  # Validation error has priority


def test_status_priority_missing_over_warnings():
    """Missing fields have higher priority than warnings."""
    record = create_base_record()
    
    # Has both missing field and uncertain field
    record.patient_last_name.extraction_state = ExtractionState.missing
    record.patient_last_name.normalized_value = None
    record.patient_last_name.review_state = ReviewState.needs_review
    
    record.patient_first_name.extraction_state = ExtractionState.uncertain
    record.patient_first_name.review_state = ReviewState.needs_review
    
    status = calculate_record_status(record, [])
    assert status == "דורש השלמה"  # Missing has priority


def test_status_priority_warnings_over_verified():
    """Unresolved warnings have higher priority than partial verification."""
    record = create_base_record()
    
    # Some fields verified, one uncertain
    record.patient_first_name.review_state = ReviewState.human_verified
    record.patient_first_name.reviewed_value = "ישראל"
    
    record.patient_id_number.extraction_state = ExtractionState.uncertain
    record.patient_id_number.review_state = ReviewState.needs_review
    
    status = calculate_record_status(record, [])
    assert status == "דורש בדיקה"  # Warning has priority over partial verification


def test_status_confirmed_empty_not_missing():
    """Confirmed empty field (human_verified with empty value) doesn't count as missing."""
    record = create_base_record()
    
    # Confirm first_name as empty
    record.patient_first_name.reviewed_value = ""
    record.patient_first_name.review_state = ReviewState.human_verified
    record.patient_first_name.extraction_state = ExtractionState.missing
    
    # All other fields normal
    status = calculate_record_status(record, [])
    
    # Should not be "דורש השלמה" because empty is confirmed
    # Should be "אושר ידנית" if other fields pending, or "תקין" if all OK
    assert status in ["תקין", "אושר ידנית"]
