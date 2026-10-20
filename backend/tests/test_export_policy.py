"""Test strict export policy with uncertain/conflicting states.

Tests verify that:
1. Uncertain extraction without human review blocks export
2. Conflicting extraction without human review blocks export  
3. Uncertain extraction with human_verified allows export
4. Conflicting extraction with human_verified allows export
5. Original extraction_state is preserved (audit trail)
"""
import pytest
from app.domain.models import (
    TestRecord, FieldValue, CommitmentRecord,
    ExtractionState, ReviewState
)
from app.services.classification.classifier import is_field_blocking_export
from app.api.process import _check_export_eligibility


def create_test_record_with_field(
    field_name: str,
    raw_value: str,
    normalized_value: str,
    reviewed_value: str | None,
    extraction_state: ExtractionState,
    review_state: ReviewState
) -> TestRecord:
    """Helper to create a TestRecord with specified field state."""
    record = TestRecord(
        test_id="test_123",
        document_id="doc_001",
        page_indices=[0]
    )
    
    # Set all required fields to valid defaults
    record.patient_first_name = FieldValue[str](
        raw_value="ישראל",
        normalized_value="ישראל",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending
    )
    record.patient_last_name = FieldValue[str](
        raw_value="ישראלי",
        normalized_value="ישראלי",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending
    )
    record.patient_id_number = FieldValue[str](
        raw_value="123456789",
        normalized_value="123456789",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending
    )
    record.sender = FieldValue[str](
        raw_value="מכבי",
        normalized_value="מכבי",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending
    )
    record.received_date = FieldValue[str](
        raw_value="2024-01-15",
        normalized_value="2024-01-15",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending
    )
    record.central_numbers = FieldValue[list[str]](
        raw_value=["12345"],
        normalized_value=["12345"],
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending
    )
    
    # Override the specified field
    field = FieldValue[str](
        raw_value=raw_value,
        normalized_value=normalized_value,
        reviewed_value=reviewed_value,
        extraction_state=extraction_state,
        review_state=review_state
    )
    setattr(record, field_name, field)
    
    return record


def test_uncertain_extraction_unresolved_blocks_export():
    """Uncertain extraction without human review blocks export."""
    record = create_test_record_with_field(
        field_name="patient_first_name",
        raw_value="ישראל",
        normalized_value="ישראל",
        reviewed_value=None,
        extraction_state=ExtractionState.uncertain,
        review_state=ReviewState.needs_review
    )
    
    # Check field-level blocking
    assert is_field_blocking_export(record.patient_first_name) is True
    
    # Check record-level blocking
    can_export, blockers = _check_export_eligibility([record], [])
    assert can_export is False
    assert len(blockers) > 0
    assert "patient_first_name" in blockers[0]


def test_conflicting_extraction_unresolved_blocks_export():
    """Conflicting extraction without human review blocks export."""
    record = create_test_record_with_field(
        field_name="patient_id_number",
        raw_value="12345678",
        normalized_value="12345678",
        reviewed_value=None,
        extraction_state=ExtractionState.conflicting,
        review_state=ReviewState.needs_review
    )
    
    # Check field-level blocking
    assert is_field_blocking_export(record.patient_id_number) is True
    
    # Check record-level blocking
    can_export, blockers = _check_export_eligibility([record], [])
    assert can_export is False
    assert len(blockers) > 0


def test_uncertain_extraction_human_verified_allows_export():
    """Uncertain extraction with human_verified allows export."""
    record = create_test_record_with_field(
        field_name="patient_first_name",
        raw_value="ישראל",
        normalized_value="ישראל",
        reviewed_value="ישראל",  # Human confirmed
        extraction_state=ExtractionState.uncertain,  # Original state preserved
        review_state=ReviewState.human_verified
    )
    
    # Check field-level blocking
    assert is_field_blocking_export(record.patient_first_name) is False
    
    # Check record-level blocking (all other fields valid, no other blockers)
    can_export, blockers = _check_export_eligibility([record], [])
    assert can_export is True
    assert len(blockers) == 0


def test_conflicting_extraction_resolved_allows_export():
    """Conflicting extraction resolved by secretary allows export."""
    record = create_test_record_with_field(
        field_name="patient_id_number",
        raw_value="12345678",
        normalized_value="12345678",
        reviewed_value="123456789",  # Secretary corrected
        extraction_state=ExtractionState.conflicting,  # Preserved for audit
        review_state=ReviewState.human_verified
    )
    
    # Check field-level blocking
    assert is_field_blocking_export(record.patient_id_number) is False
    
    # Check record-level blocking
    can_export, blockers = _check_export_eligibility([record], [])
    assert can_export is True
    assert len(blockers) == 0


def test_extraction_state_preserved():
    """Verify that original extraction_state is preserved for audit trail."""
    record = create_test_record_with_field(
        field_name="sender",
        raw_value="מכבי",
        normalized_value="מכבי",
        reviewed_value="מכבי שירותי בריאות",  # Human enhanced
        extraction_state=ExtractionState.uncertain,
        review_state=ReviewState.human_verified
    )
    
    # After human verification, extraction_state should remain unchanged
    assert record.sender.extraction_state == ExtractionState.uncertain
    assert record.sender.review_state == ReviewState.human_verified
    
    # But export should be allowed because human_verified
    assert is_field_blocking_export(record.sender) is False


def test_invalid_extraction_blocks_until_verified():
    """Invalid extraction blocks export until human_verified."""
    # Unresolved invalid → blocks
    record_invalid = create_test_record_with_field(
        field_name="patient_id_number",
        raw_value="invalid",
        normalized_value="invalid",
        reviewed_value=None,
        extraction_state=ExtractionState.invalid,
        review_state=ReviewState.needs_review
    )
    assert is_field_blocking_export(record_invalid.patient_id_number) is True
    
    # Resolved invalid → allows
    record_fixed = create_test_record_with_field(
        field_name="patient_id_number",
        raw_value="invalid",
        normalized_value="invalid",
        reviewed_value="123456789",  # Human corrected
        extraction_state=ExtractionState.invalid,  # Preserved
        review_state=ReviewState.human_verified
    )
    assert is_field_blocking_export(record_fixed.patient_id_number) is False


def test_needs_review_blocks_until_verified():
    """needs_review state blocks export until human_verified."""
    record = create_test_record_with_field(
        field_name="received_date",
        raw_value="2024-01-15",
        normalized_value="2024-01-15",
        reviewed_value=None,
        extraction_state=ExtractionState.found,
        review_state=ReviewState.needs_review
    )
    
    # Unresolved needs_review → blocks
    assert is_field_blocking_export(record.received_date) is True
    
    # After human verification
    record.received_date.review_state = ReviewState.human_verified
    record.received_date.reviewed_value = "2024-01-15"
    assert is_field_blocking_export(record.received_date) is False


def test_confirmed_empty_allowed_for_confirmable_fields():
    """Fields that can be confirmed empty don't block export when human_verified."""
    # first_name can be confirmed empty
    record = create_test_record_with_field(
        field_name="patient_first_name",
        raw_value="",
        normalized_value="",
        reviewed_value="",  # Confirmed empty
        extraction_state=ExtractionState.missing,
        review_state=ReviewState.human_verified
    )
    
    # Should not block because human_verified (even though empty)
    assert is_field_blocking_export(record.patient_first_name) is False
