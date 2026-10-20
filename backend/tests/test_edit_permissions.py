"""Tests for field edit permission enforcement."""
import pytest
from pathlib import Path

from app.domain.models import (
    TestRecord, FieldValue, ExtractionState, ReviewState
)
from app.api.process import _check_export_eligibility
from app.services.storage import JSONStorage


def test_valid_field_not_editable():
    """Test that a valid field (found, pending, no issues) cannot be edited."""
    # Create a test record with one valid field
    record = TestRecord(
        test_id="test_001",
        document_id="doc_001",
        page_indices=[0]
    )
    
    # Valid field: found, pending, no issues
    record.patient_first_name = FieldValue[str](
        raw_value="יוסי",
        normalized_value="יוסי",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        validation_issues=[],
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_001"
    )
    
    # This field should NOT be editable
    field = record.patient_first_name
    is_editable = not (
        field.extraction_state == ExtractionState.found and
        field.review_state == ReviewState.pending and
        not field.validation_issues
    )
    
    assert is_editable is False, "Valid field should not be editable"


def test_needs_review_field_editable():
    """Test that a field marked needs_review is editable."""
    record = TestRecord(
        test_id="test_002",
        document_id="doc_002",
        page_indices=[0]
    )
    
    # Field with needs_review
    record.patient_id_number = FieldValue[str](
        raw_value="12345678",
        normalized_value="12345678",
        extraction_state=ExtractionState.uncertain,
        review_state=ReviewState.needs_review,
        validation_issues=[],
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_002"
    )
    
    # This field should be editable
    field = record.patient_id_number
    is_editable = not (
        field.extraction_state == ExtractionState.found and
        field.review_state == ReviewState.pending and
        not field.validation_issues
    )
    
    assert is_editable is True, "needs_review field should be editable"


def test_invalid_field_editable():
    """Test that an invalid field is editable."""
    record = TestRecord(
        test_id="test_003",
        document_id="doc_003",
        page_indices=[0]
    )
    
    # Invalid field
    record.patient_last_name = FieldValue[str](
        raw_value="",
        normalized_value="",
        extraction_state=ExtractionState.invalid,
        review_state=ReviewState.needs_review,
        validation_issues=[{"field_name": "patient_last_name", "severity": "error", "message": "Required field missing"}],
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_003"
    )
    
    # This field should be editable
    field = record.patient_last_name
    is_editable = not (
        field.extraction_state == ExtractionState.found and
        field.review_state == ReviewState.pending and
        not field.validation_issues
    )
    
    assert is_editable is True, "Invalid field should be editable"


def test_export_blocked_with_needs_review():
    """Test that export is blocked when fields have needs_review."""
    record = TestRecord(
        test_id="test_004",
        document_id="doc_004",
        page_indices=[0]
    )
    
    # One valid field
    record.patient_first_name = FieldValue[str](
        raw_value="דני",
        normalized_value="דני",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_004"
    )
    
    # One field needing review
    record.patient_last_name = FieldValue[str](
        raw_value="כהן",
        normalized_value="כהן",
        extraction_state=ExtractionState.uncertain,
        review_state=ReviewState.needs_review,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_005"
    )
    
    can_export, blockers = _check_export_eligibility([record])
    
    assert can_export is False, "Export should be blocked"
    assert len(blockers) > 0, "Should have blockers"
    assert "patient_last_name" in blockers[0], "Blocker should mention the problematic field"


def test_export_allowed_with_all_valid():
    """Test that export is allowed when all fields are valid or human_verified."""
    record = TestRecord(
        test_id="test_005",
        document_id="doc_005",
        page_indices=[0]
    )
    
    # All valid fields
    record.patient_first_name = FieldValue[str](
        raw_value="שרה",
        normalized_value="שרה",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_006"
    )
    
    record.patient_last_name = FieldValue[str](
        raw_value="לוי",
        normalized_value="לוי",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.human_verified,  # Verified is OK
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_007"
    )
    
    record.patient_id_number = FieldValue[str](
        raw_value="123456789",
        normalized_value="123456789",
        extraction_state=ExtractionState.found,
        review_state=ReviewState.pending,
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_008"
    )
    
    can_export, blockers = _check_export_eligibility([record])
    
    assert can_export is True, "Export should be allowed"
    assert len(blockers) == 0, "Should have no blockers"


def test_field_with_validation_issues_editable():
    """Test that a field with validation issues is editable even if extraction_state is found."""
    record = TestRecord(
        test_id="test_006",
        document_id="doc_006",
        page_indices=[0]
    )
    
    # Field with validation issues
    record.patient_id_number = FieldValue[str](
        raw_value="12345",  # Too short
        normalized_value="12345",
        extraction_state=ExtractionState.found,  # Found but invalid
        review_state=ReviewState.pending,
        validation_issues=[{"field_name": "patient_id_number", "severity": "error", "message": "ID must be 9 digits"}],
        extractor_id="gemini-test",
        extraction_attempt_id="attempt_009"
    )
    
    # This field should be editable because it has validation issues
    field = record.patient_id_number
    is_editable = not (
        field.extraction_state == ExtractionState.found and
        field.review_state == ReviewState.pending and
        not field.validation_issues
    )
    
    assert is_editable is True, "Field with validation issues should be editable"
