"""Offline regression coverage for page-owned patient fields and export approval."""
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api import process
from app.domain.models import CommitmentRecord
from app.services.extraction.mock_extractor import MockExtractor
from app.services.processing.background import BackgroundProcessor
from app.services.storage.json_storage import JSONStorage


@pytest.fixture
def page_batch(tmp_path, monkeypatch):
    monkeypatch.setattr(process, '_storage', JSONStorage(tmp_path))
    monkeypatch.setattr(process.settings, 'temp_storage_path', str(tmp_path))
    # Avoid initializing any live extractor or background worker.
    processor = object.__new__(BackgroundProcessor)
    extractor = MockExtractor(simulate_delay=False)
    records = []
    for index in range(3):
        result = extractor.extract(b'', 'synthetic_document', index)
        record = processor._create_commitment_from_page(result, 'synthetic_document', index)
        assert record.patient_first_name.raw_value == result.fields['patient_first_name']
        assert record.central_numbers.raw_value == result.fields['central_numbers']
        records.append(record.model_dump(mode='json'))
    process._storage.save_batch('synthetic_batch', {'test_records': [], 'commitment_records': records})
    app = FastAPI()
    app.include_router(process.router)
    return TestClient(app)


def approve(client):
    data = process._storage.load_batch('synthetic_batch')
    for record in data['commitment_records']:
        for name in ('patient_first_name', 'patient_last_name', 'patient_id_number',
                     'sender', 'received_date', 'central_numbers', 'commitment_number'):
            response = client.post(f"/api/batches/synthetic_batch/tests/{record['commitment_record_id']}/fields/{name}/verify")
            assert response.status_code == 200


def test_page_fields_survive_storage_review_and_post_export(page_batch):
    client = page_batch
    assert client.post('/api/batches/synthetic_batch/export').status_code == 400
    approve(client)
    record = process._storage.load_batch('synthetic_batch')['commitment_records'][0]
    path = f"/api/batches/synthetic_batch/tests/{record['commitment_record_id']}/fields/patient_first_name"
    assert client.patch(path, json={'new_value': 'Corrected synthetic name'}).status_code == 200
    assert client.get('/api/batches/synthetic_batch/export-check').json()['can_export'] is True
    response = client.post('/api/batches/synthetic_batch/export')
    assert response.status_code == 200
    ws = load_workbook(BytesIO(response.content)).active
    assert (ws.max_row, ws.max_column) == (4, 7)
    stored = process._storage.load_batch('synthetic_batch')['commitment_records']
    for row, data in zip(ws.iter_rows(min_row=2, values_only=True), stored):
        record = CommitmentRecord(**data)
        assert row == (record.patient_first_name.reviewed_value or record.patient_first_name.raw_value,
                       record.patient_last_name.raw_value, record.patient_id_number.raw_value,
                       record.sender.raw_value, record.received_date.raw_value,
                       ', '.join(record.central_numbers.raw_value), record.commitment_number.raw_value)
    assert ws.cell(2, 1).value == 'Corrected synthetic name'


@pytest.mark.parametrize('name', ['patient_first_name', 'patient_last_name', 'patient_id_number',
                                 'sender', 'received_date', 'central_numbers', 'commitment_number'])
@pytest.mark.parametrize('problem', ['absent', 'empty_correction', 'unreviewed'])
def test_required_field_blockers(page_batch, name, problem):
    approve(page_batch)
    data = process._storage.load_batch('synthetic_batch')
    record = data['commitment_records'][0]
    if problem == 'absent':
        del record[name]
    elif problem == 'empty_correction':
        record[name]['reviewed_value'] = [] if name == 'central_numbers' else '   '
    else:
        record[name]['review_state'] = 'needs_review'
    process._storage.save_batch('synthetic_batch', data)
    assert page_batch.get('/api/batches/synthetic_batch/export-check').json()['can_export'] is False
    assert page_batch.post('/api/batches/synthetic_batch/export').status_code == 400


def test_empty_batch_and_unresolved_relationship_block(page_batch):
    approve(page_batch)
    data = process._storage.load_batch('synthetic_batch')
    data['commitment_records'][0]['relationship_status'] = 'unresolved_relationship'
    process._storage.save_batch('synthetic_batch', data)
    assert page_batch.post('/api/batches/synthetic_batch/export').status_code == 400
    assert process._check_export_eligibility_commitments([])[0] is False


def test_reviewed_empty_never_falls_back():
    from app.domain.models import FieldValue
    from app.services.export.excel_exporter import ExcelExporter
    assert ExcelExporter()._get_value(FieldValue[str](raw_value='original', reviewed_value='')) == ''
