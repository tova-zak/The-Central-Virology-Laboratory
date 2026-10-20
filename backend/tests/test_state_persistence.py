"""Tests for state persistence after field edits and page refresh.

Verifies that reviewed_value, review_state, and classification are preserved
after saving edits to the backend.
"""
import pytest
from pathlib import Path
from app.services.storage import JSONStorage
from app.domain.models import TestRecord, FieldValue, ExtractionState, ReviewState
from app.services.classification.classifier import classify_record


def test_reviewed_value_persists_after_save():
    """Test that reviewed_value is saved and persists across reloads."""
    batch_id = "test_batch_persistence"
    storage = JSONStorage(base_path=Path("temp"))
    
    # Initial record with uncertain field
    batch_data = {
        "batch_id": batch_id,
        "status": "completed",
        "test_records": [
            {
                "test_id": "test_001",
                "document_id": "doc_001",
                "page_indices": [0],
                "patient_first_name": {
                    "raw_value": "ישראל",
                    "normalized_value": "ישראל",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "patient_last_name": {
                    "raw_value": "ישראלי",
                    "normalized_value": "ישראלי",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "patient_id_number": {
                    "raw_value": "123456789",
                    "normalized_value": "123456789",
                    "reviewed_value": None,
                    "extraction_state": "uncertain",  # Needs review
                    "review_state": "pending",
                    "validation_issues": []
                },
                "sender": {
                    "raw_value": "מעבדה",
                    "normalized_value": "מעבדה",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "received_date": {
                    "raw_value": "2024-01-01",
                    "normalized_value": "2024-01-01",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "central_numbers": {
                    "raw_value": ["12345"],
                    "normalized_value": ["12345"],
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "commitment_ids": []
            }
        ],
        "commitment_records": []
    }
    
    storage.save_batch(batch_id, batch_data)
    
    # Verify initial classification (warnings table)
    loaded_data = storage.load_batch(batch_id)
    record_dict = loaded_data["test_records"][0]
    record = TestRecord(**record_dict)
    assert classify_record(record) == 'warnings'
    
    # Simulate human edit: approve uncertain field
    record_dict["patient_id_number"]["reviewed_value"] = "123456789"
    record_dict["patient_id_number"]["review_state"] = "human_verified"
    
    # Save the edit
    storage.save_batch(batch_id, loaded_data)
    
    # Simulate page refresh - reload from storage
    refreshed_data = storage.load_batch(batch_id)
    refreshed_record_dict = refreshed_data["test_records"][0]
    refreshed_record = TestRecord(**refreshed_record_dict)
    
    # Verify reviewed_value persisted
    assert refreshed_record.patient_id_number.reviewed_value == "123456789"
    assert refreshed_record.patient_id_number.review_state == ReviewState.human_verified
    
    # Verify raw_value unchanged
    assert refreshed_record.patient_id_number.raw_value == "123456789"
    assert refreshed_record.patient_id_number.normalized_value == "123456789"
    
    # Verify extraction_state preserved
    assert refreshed_record.patient_id_number.extraction_state == ExtractionState.uncertain
    
    # Verify classification updated (now success table)
    assert classify_record(refreshed_record) == 'success'


def test_raw_value_never_modified_by_edit():
    """Test that raw_value is never changed when user edits a field."""
    batch_id = "test_batch_raw_preserve"
    storage = JSONStorage(base_path=Path("temp"))
    
    original_raw = "original_value"
    new_reviewed = "corrected_value"
    
    batch_data = {
        "batch_id": batch_id,
        "status": "completed",
        "test_records": [
            {
                "test_id": "test_002",
                "document_id": "doc_002",
                "page_indices": [0],
                "patient_first_name": {
                    "raw_value": original_raw,
                    "normalized_value": original_raw,
                    "reviewed_value": None,
                    "extraction_state": "uncertain",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "patient_last_name": {
                    "raw_value": "כהן",
                    "normalized_value": "כהן",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "patient_id_number": {
                    "raw_value": "987654321",
                    "normalized_value": "987654321",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "sender": {
                    "raw_value": "מרכז",
                    "normalized_value": "מרכז",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "received_date": {
                    "raw_value": "2024-02-20",
                    "normalized_value": "2024-02-20",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "central_numbers": {
                    "raw_value": ["67890"],
                    "normalized_value": ["67890"],
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "commitment_ids": []
            }
        ],
        "commitment_records": []
    }
    
    storage.save_batch(batch_id, batch_data)
    
    # Simulate edit - ONLY change reviewed_value
    loaded_data = storage.load_batch(batch_id)
    record_dict = loaded_data["test_records"][0]
    
    record_dict["patient_first_name"]["reviewed_value"] = new_reviewed
    record_dict["patient_first_name"]["review_state"] = "human_verified"
    # DO NOT touch raw_value or normalized_value
    
    storage.save_batch(batch_id, loaded_data)
    
    # Reload and verify
    reloaded_data = storage.load_batch(batch_id)
    reloaded_record_dict = reloaded_data["test_records"][0]
    
    # raw_value must be unchanged
    assert reloaded_record_dict["patient_first_name"]["raw_value"] == original_raw
    
    # reviewed_value must be new value
    assert reloaded_record_dict["patient_first_name"]["reviewed_value"] == new_reviewed
    
    # review_state must be updated
    assert reloaded_record_dict["patient_first_name"]["review_state"] == "human_verified"


def test_classification_correct_after_multiple_edits():
    """Test that classification remains correct after multiple field edits and reloads."""
    batch_id = "test_batch_multi_edit"
    storage = JSONStorage(base_path=Path("temp"))
    
    batch_data = {
        "batch_id": batch_id,
        "status": "completed",
        "test_records": [
            {
                "test_id": "test_003",
                "document_id": "doc_003",
                "page_indices": [0],
                "patient_first_name": {
                    "raw_value": None,  # Missing
                    "normalized_value": None,
                    "reviewed_value": None,
                    "extraction_state": "missing",
                    "review_state": "needs_review",
                    "validation_issues": []
                },
                "patient_last_name": {
                    "raw_value": "לוי",
                    "normalized_value": "לוי",
                    "reviewed_value": None,
                    "extraction_state": "uncertain",  # Warning
                    "review_state": "pending",
                    "validation_issues": []
                },
                "patient_id_number": {
                    "raw_value": "111222333",
                    "normalized_value": "111222333",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "sender": {
                    "raw_value": "בית חולים",
                    "normalized_value": "בית חולים",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "received_date": {
                    "raw_value": "2024-03-10",
                    "normalized_value": "2024-03-10",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "central_numbers": {
                    "raw_value": ["11111"],
                    "normalized_value": ["11111"],
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "commitment_ids": []
            }
        ],
        "commitment_records": []
    }
    
    storage.save_batch(batch_id, batch_data)
    
    # Initial: missing table (priority: missing > warnings)
    data1 = storage.load_batch(batch_id)
    record1 = TestRecord(**data1["test_records"][0])
    assert classify_record(record1) == 'missing'
    
    # Edit 1: Fix missing field
    data1["test_records"][0]["patient_first_name"]["reviewed_value"] = "דוד"
    data1["test_records"][0]["patient_first_name"]["review_state"] = "human_verified"
    data1["test_records"][0]["patient_first_name"]["extraction_state"] = "found"
    storage.save_batch(batch_id, data1)
    
    # After edit 1: warnings table (still has uncertain last_name)
    data2 = storage.load_batch(batch_id)
    record2 = TestRecord(**data2["test_records"][0])
    assert classify_record(record2) == 'warnings'
    
    # Edit 2: Fix warning field
    data2["test_records"][0]["patient_last_name"]["reviewed_value"] = "לוי"
    data2["test_records"][0]["patient_last_name"]["review_state"] = "human_verified"
    storage.save_batch(batch_id, data2)
    
    # After edit 2: success table (all resolved)
    data3 = storage.load_batch(batch_id)
    record3 = TestRecord(**data3["test_records"][0])
    assert classify_record(record3) == 'success'
    
    # Simulate page refresh - verify still success
    data4 = storage.load_batch(batch_id)
    record4 = TestRecord(**data4["test_records"][0])
    assert classify_record(record4) == 'success'
