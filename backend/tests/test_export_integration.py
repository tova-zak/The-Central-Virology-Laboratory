"""Integration tests for Excel export functionality.

Tests the complete export flow from button click to file download.
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.storage import JSONStorage
from app.domain.models import TestRecord, CommitmentRecord, FieldValue, ExtractionState, ReviewState

client = TestClient(app)


def test_export_blocked_when_uncertain_field_not_resolved():
    """Test that export endpoint blocks when uncertain field is not human_verified."""
    # Create test batch with uncertain field
    batch_id = "test_batch_export_blocked"
    storage = JSONStorage(base_path=Path("temp"))
    
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
                    "extraction_state": "uncertain",  # BLOCKER
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
    
    # Try to export - should be blocked
    response = client.post(f"/api/batches/{batch_id}/export")
    
    assert response.status_code == 400
    assert "Export blocked" in response.json()["detail"]["message"]
    assert len(response.json()["detail"]["problematic_records"]) == 1
    assert "patient_id_number" in response.json()["detail"]["problematic_records"][0]["issues"]


def test_export_succeeds_after_human_verification():
    """Test that export works after all uncertain fields are human_verified."""
    batch_id = "test_batch_export_success"
    storage = JSONStorage(base_path=Path("temp"))
    
    batch_data = {
        "batch_id": batch_id,
        "status": "completed",
        "test_records": [
            {
                "test_id": "test_002",
                "document_id": "doc_002",
                "page_indices": [0],
                "patient_first_name": {
                    "raw_value": "שרה",
                    "normalized_value": "שרה",
                    "reviewed_value": "שרה",
                    "extraction_state": "found",
                    "review_state": "human_verified",
                    "validation_issues": []
                },
                "patient_last_name": {
                    "raw_value": "כהן",
                    "normalized_value": "כהן",
                    "reviewed_value": "כהן",
                    "extraction_state": "found",
                    "review_state": "human_verified",
                    "validation_issues": []
                },
                "patient_id_number": {
                    "raw_value": "987654321",
                    "normalized_value": "987654321",
                    "reviewed_value": "987654321",
                    "extraction_state": "uncertain",  # WAS uncertain
                    "review_state": "human_verified",  # BUT now verified
                    "validation_issues": []
                },
                "sender": {
                    "raw_value": "מרכז רפואי",
                    "normalized_value": "מרכז רפואי",
                    "reviewed_value": "מרכז רפואי",
                    "extraction_state": "found",
                    "review_state": "human_verified",
                    "validation_issues": []
                },
                "received_date": {
                    "raw_value": "2024-02-20",
                    "normalized_value": "2024-02-20",
                    "reviewed_value": "2024-02-20",
                    "extraction_state": "found",
                    "review_state": "human_verified",
                    "validation_issues": []
                },
                "central_numbers": {
                    "raw_value": ["67890"],
                    "normalized_value": ["67890"],
                    "reviewed_value": ["67890"],
                    "extraction_state": "found",
                    "review_state": "human_verified",
                    "validation_issues": []
                },
                "commitment_ids": []
            }
        ],
        "commitment_records": []
    }
    
    storage.save_batch(batch_id, batch_data)
    
    # Export should succeed now
    response = client.post(f"/api/batches/{batch_id}/export")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "commitments_" in response.headers["content-disposition"]
    assert len(response.content) > 0  # Excel file has content


def test_export_check_endpoint_separate_from_export():
    """Test that export-check endpoint does not trigger actual export."""
    batch_id = "test_batch_check"
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
                    "raw_value": "דוד",
                    "normalized_value": "דוד",
                    "reviewed_value": None,
                    "extraction_state": "found",
                    "review_state": "pending",
                    "validation_issues": []
                },
                "patient_last_name": {
                    "raw_value": "לוי",
                    "normalized_value": "לוי",
                    "reviewed_value": None,
                    "extraction_state": "found",
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
    
    # Call export-check (GET endpoint)
    response = client.get(f"/api/batches/{batch_id}/export-check")
    
    # Should return JSON, not Excel file
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "can_export" in response.json()
    assert response.json()["can_export"] == True  # All fields are valid
    
    # Verify no Excel file was created (export-check should not create files)
    batch_dir = Path("temp") / batch_id
    if batch_dir.exists():
        export_files = list(batch_dir.glob("*_export.xlsx"))
        # If files exist from previous export test, that's ok, but count should not increase
        initial_count = len(export_files)
    
    # Call export-check again
    response2 = client.get(f"/api/batches/{batch_id}/export-check")
    assert response2.status_code == 200
    
    # Verify still no new files created
    if batch_dir.exists():
        export_files_after = list(batch_dir.glob("*_export.xlsx"))
        assert len(export_files_after) == initial_count  # No new files
