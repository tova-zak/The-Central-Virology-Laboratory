"""Test export-check endpoint with one-page-one-commitment model.

Verifies:
- HTTP 200 response (no KeyError on missing test_records)
- Correct blocking logic for pending/incomplete/needs_review/invalid states
- Correct approval for fully reviewed approved commitments
"""
import pytest
from app.api.process import _check_export_eligibility_commitments


def test_export_check_all_approved():
    """Fully reviewed and approved commitments can export."""
    commitment_records = [
        {
            "commitment_id": "cmt_001",
            "status": "approved",
            "patient_first_name": {
                "extraction_state": "found",
                "review_state": "approved"
            },
            "patient_last_name": {
                "extraction_state": "found",
                "review_state": "approved"
            },
            "patient_id_number": {
                "extraction_state": "found",
                "review_state": "approved"
            },
            "test_date": {
                "extraction_state": "found",
                "review_state": "approved"
            },
            "test_type": {
                "extraction_state": "found",
                "review_state": "approved"
            },
            "test_result": {
                "extraction_state": "found",
                "review_state": "approved"
            }
        }
    ]
    
    can_export, blockers = _check_export_eligibility_commitments(commitment_records)
    
    assert can_export is True
    assert blockers == []


def test_export_check_blocked_pending():
    """Pending commitments block export."""
    commitment_records = [
        {
            "commitment_id": "cmt_pending",
            "status": "pending"
        }
    ]
    
    can_export, blockers = _check_export_eligibility_commitments(commitment_records)
    
    assert can_export is False
    assert "cmt_pending: pending_extraction" in blockers


def test_export_check_blocked_incomplete():
    """Incomplete commitments block export."""
    commitment_records = [
        {
            "commitment_id": "cmt_incomplete",
            "status": "incomplete"
        }
    ]
    
    can_export, blockers = _check_export_eligibility_commitments(commitment_records)
    
    assert can_export is False
    assert "cmt_incomplete: incomplete_extraction" in blockers


def test_export_check_blocked_needs_review():
    """Fields with needs_review state block export."""
    commitment_records = [
        {
            "commitment_id": "cmt_review",
            "status": "approved",
            "patient_first_name": {
                "extraction_state": "found",
                "review_state": "needs_review"
            }
        }
    ]
    
    can_export, blockers = _check_export_eligibility_commitments(commitment_records)
    
    assert can_export is False
    assert "cmt_review: patient_first_name_needs_review" in blockers


def test_export_check_blocked_invalid():
    """Fields with invalid extraction_state block export."""
    commitment_records = [
        {
            "commitment_id": "cmt_invalid",
            "status": "approved",
            "patient_id_number": {
                "extraction_state": "invalid",
                "review_state": "approved"
            }
        }
    ]
    
    can_export, blockers = _check_export_eligibility_commitments(commitment_records)
    
    assert can_export is False
    assert "cmt_invalid: patient_id_number_invalid" in blockers


def test_export_check_mixed_multiple_blockers():
    """Multiple commitments with multiple blockers."""
    commitment_records = [
        {
            "commitment_id": "cmt_ok",
            "status": "approved",
            "patient_first_name": {"extraction_state": "found", "review_state": "approved"}
        },
        {
            "commitment_id": "cmt_pending",
            "status": "pending"
        },
        {
            "commitment_id": "cmt_needs_review",
            "status": "approved",
            "test_result": {"extraction_state": "found", "review_state": "needs_review"}
        }
    ]
    
    can_export, blockers = _check_export_eligibility_commitments(commitment_records)
    
    assert can_export is False
    assert "cmt_pending: pending_extraction" in blockers
    assert "cmt_needs_review: test_result_needs_review" in blockers
    assert len(blockers) == 2
