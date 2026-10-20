"""Integration tests for record reclassification after field edits.

Tests that records move between tables (missing → warnings → success)
after fields are fixed and approved by human review.
"""
import pytest
from app.domain.models import TestRecord, FieldValue, ExtractionState, ReviewState
from app.services.classification.classifier import classify_record


def test_record_moves_from_missing_to_warnings_after_fix():
    """Test that a record with missing field moves to warnings table after field is filled."""
    # Create record with missing last_name
    record = TestRecord(
        test_id="test_001",
        document_id="doc_001",
        page_indices=[0],
        patient_first_name=FieldValue(
            raw_value="ישראל",
            normalized_value="ישראל",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        patient_last_name=FieldValue(
            raw_value=None,
            normalized_value=None,
            reviewed_value=None,
            extraction_state=ExtractionState.missing,
            review_state=ReviewState.needs_review,
            validation_issues=[]
        ),
        patient_id_number=FieldValue(
            raw_value="123456789",
            normalized_value="123456789",
            reviewed_value=None,
            extraction_state=ExtractionState.uncertain,  # Has warning
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        sender=FieldValue(
            raw_value="מעבדת מגן",
            normalized_value="מעבדת מגן",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        received_date=FieldValue(
            raw_value="2024-01-15",
            normalized_value="2024-01-15",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        central_numbers=FieldValue(
            raw_value=["12345"],
            normalized_value=["12345"],
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        commitment_ids=[]
    )
    
    # Initially should be in missing table (Table 3)
    classification = classify_record(record)
    assert classification == 'missing', "Record with missing field should be in Table 3"
    
    # Fix the missing field by adding human-verified value
    record.patient_last_name.reviewed_value = "ישראלי"
    record.patient_last_name.review_state = ReviewState.human_verified
    record.patient_last_name.extraction_state = ExtractionState.found
    
    # Now should be in warnings table (Table 2) because ID is uncertain
    classification = classify_record(record)
    assert classification == 'warnings', "Record with resolved missing field but uncertain ID should be in Table 2"


def test_record_moves_from_warnings_to_success_after_verify():
    """Test that a record with warnings moves to success table after all warnings are resolved."""
    # Create record with uncertain extraction
    record = TestRecord(
        test_id="test_002",
        document_id="doc_002",
        page_indices=[1],
        patient_first_name=FieldValue(
            raw_value="שרה",
            normalized_value="שרה",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        patient_last_name=FieldValue(
            raw_value="כהן",
            normalized_value="כהן",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        patient_id_number=FieldValue(
            raw_value="987654321",
            normalized_value="987654321",
            reviewed_value=None,
            extraction_state=ExtractionState.uncertain,  # Warning
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        sender=FieldValue(
            raw_value="מרכז רפואי",
            normalized_value="מרכז רפואי",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        received_date=FieldValue(
            raw_value="2024-02-20",
            normalized_value="2024-02-20",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        central_numbers=FieldValue(
            raw_value=["67890"],
            normalized_value=["67890"],
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        commitment_ids=[]
    )
    
    # Initially should be in warnings table (Table 2)
    classification = classify_record(record)
    assert classification == 'warnings', "Record with uncertain field should be in Table 2"
    
    # Verify the uncertain field
    record.patient_id_number.reviewed_value = "987654321"
    record.patient_id_number.review_state = ReviewState.human_verified
    
    # Now should be in success table (Table 1)
    classification = classify_record(record)
    assert classification == 'success', "Record with all fields verified should be in Table 1"


def test_record_stays_in_missing_until_all_missing_fields_fixed():
    """Test that a record stays in missing table until ALL missing fields are fixed."""
    # Create record with two missing fields
    record = TestRecord(
        test_id="test_003",
        document_id="doc_003",
        page_indices=[2],
        patient_first_name=FieldValue(
            raw_value=None,
            normalized_value=None,
            reviewed_value=None,
            extraction_state=ExtractionState.missing,
            review_state=ReviewState.needs_review,
            validation_issues=[]
        ),
        patient_last_name=FieldValue(
            raw_value=None,
            normalized_value=None,
            reviewed_value=None,
            extraction_state=ExtractionState.missing,
            review_state=ReviewState.needs_review,
            validation_issues=[]
        ),
        patient_id_number=FieldValue(
            raw_value="111222333",
            normalized_value="111222333",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        sender=FieldValue(
            raw_value="בית חולים",
            normalized_value="בית חולים",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        received_date=FieldValue(
            raw_value="2024-03-10",
            normalized_value="2024-03-10",
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        central_numbers=FieldValue(
            raw_value=["11111"],
            normalized_value=["11111"],
            reviewed_value=None,
            extraction_state=ExtractionState.found,
            review_state=ReviewState.pending,
            validation_issues=[]
        ),
        commitment_ids=[]
    )
    
    # Initially in missing table
    classification = classify_record(record)
    assert classification == 'missing'
    
    # Fix only first_name
    record.patient_first_name.reviewed_value = "דוד"
    record.patient_first_name.review_state = ReviewState.human_verified
    record.patient_first_name.extraction_state = ExtractionState.found
    
    # Still in missing table because last_name is still missing
    classification = classify_record(record)
    assert classification == 'missing', "Record should stay in missing table until ALL missing fields are fixed"
    
    # Fix last_name too
    record.patient_last_name.reviewed_value = "לוי"
    record.patient_last_name.review_state = ReviewState.human_verified
    record.patient_last_name.extraction_state = ExtractionState.found
    
    # Now should move to success table
    classification = classify_record(record)
    assert classification == 'success', "Record should move to success after all missing fields are fixed"
