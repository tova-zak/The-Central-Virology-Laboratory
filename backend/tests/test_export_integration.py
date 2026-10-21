"""Integration tests for Excel export (commitment_records model, offline).

Storage is a JSONStorage under a pytest temp dir patched into app.api.process; no Supabase, no network.
"""
import pytest
from fastapi.testclient import TestClient

from app.api import process
from app.domain.models import CommitmentRecord, ExtractionState, FieldValue, ReviewState
from app.services.storage import JSONStorage


def _field(value, verified=True):
    return FieldValue(
        raw_value=value,
        normalized_value=value,
        extraction_state=ExtractionState.found,
        review_state=ReviewState.human_verified if verified else ReviewState.pending,
    )


def _record(record_id="rec_001", unreviewed=()):
    values = dict(
        patient_first_name="FIRST_01",
        patient_last_name="LAST_01",
        patient_id_number="000000018",
        sender="SENDER_PLACEHOLDER",
        received_date="01/01/2026",
        central_numbers=["100001"],
        commitment_number="200001",
    )
    fields = {name: _field(value, name not in unreviewed) for name, value in values.items()}
    return CommitmentRecord(
        commitment_record_id=record_id, form_id=f"{record_id}_page_1",
        status="complete", relationship_status="inferred", **fields,
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    from app.main import app
    storage = JSONStorage(base_path=tmp_path)
    monkeypatch.setattr(process, "_storage", storage)
    monkeypatch.setattr(process.settings, "temp_storage_path", str(tmp_path))
    return TestClient(app), storage


def _save(storage, record, batch_id):
    storage.save_batch(batch_id, {
        "batch_id": batch_id,
        "status": "completed",
        "test_records": [],
        "commitment_records": [record.model_dump(mode="json")],
    })
    return batch_id


def test_export_blocked_when_uncertain_field_not_resolved(client):
    """Export is blocked while a field is not human_verified."""
    http, storage = client
    batch_id = _save(storage, _record(unreviewed=("patient_id_number",)), "test_batch_export_blocked")

    response = http.post(f"/api/batches/{batch_id}/export")

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Export blocked" in detail["message"]
    assert "rec_001: patient_id_number_unreviewed" in detail["blockers"]


def test_export_succeeds_after_human_verification(client):
    """Export works once every field is human_verified."""
    http, storage = client
    batch_id = _save(storage, _record(), "test_batch_export_success")

    response = http.post(f"/api/batches/{batch_id}/export")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "commitments_" in response.headers["content-disposition"]
    assert len(response.content) > 0


def test_export_check_endpoint_separate_from_export(client, tmp_path):
    """export-check reports eligibility as JSON and never creates an export file."""
    http, storage = client
    blocked = _save(storage, _record("rec_blocked", unreviewed=("sender",)), "test_batch_check_blocked")
    ready = _save(storage, _record("rec_ready"), "test_batch_check_ready")

    response = http.get(f"/api/batches/{blocked}/export-check")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json()["can_export"] is False
    assert "rec_blocked: sender_unreviewed" in response.json()["blockers"]

    response = http.get(f"/api/batches/{ready}/export-check")
    assert response.status_code == 200
    assert response.json() == {"can_export": True, "blockers": []}

    assert list(tmp_path.rglob("*_export.xlsx")) == []
