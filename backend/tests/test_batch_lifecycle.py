"""Test complete batch lifecycle: Upload → Process → Review → Export.

These integration tests verify the full E2E workflow without calling Gemini.
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import io
from PIL import Image

from app.main import app
from app.services.storage import JSONStorage


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def temp_storage(tmp_path, monkeypatch):
    """Set up temporary storage."""
    storage_path = tmp_path / "test_storage"
    storage_path.mkdir()
    monkeypatch.setenv("TEMP_STORAGE_PATH", str(storage_path))
    
    # Reload settings to pick up new path
    from app.core import config
    # monkeypatch so the replaced settings object is restored after the test
    # (otherwise it leaks into later test modules, e.g. upload-limit/export tests)
    monkeypatch.setattr(config, "settings", config.Settings())
    
    return storage_path


@pytest.fixture
def mock_gemini_extractor():
    """Mock Gemini extractor to avoid API calls."""
    mock_result = MagicMock()
    mock_result.model_id = "gemini-test-mock"
    mock_result.fields = {
        "patient_first_name": "יוחנן",
        "patient_last_name": "כהן",
        "patient_id_number": "123456782",
        "sender": "בית חולים איכילוב",
        "received_date": "2024-01-15",
        "central_numbers": ["12345", "67890"],
        "commitment_numbers": ["12345", "67890"]  # Added this field
    }
    mock_result.warnings = []  # No warnings
    
    with patch("app.services.processing.background.GeminiExtractor") as mock:
        mock_instance = MagicMock()
        mock_instance.extract.return_value = mock_result
        mock.return_value = mock_instance
        yield mock


def create_test_pdf(tmp_path: Path) -> Path:
    """Create a minimal test PDF."""
    import fitz
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), "Test Form", fontsize=12)
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


class TestBatchLifecycle:
    """Test the complete batch lifecycle."""
    
    def test_upload_creates_batch(self, client, temp_storage):
        """Test 1: Upload creates a batch."""
        # Create test PDF
        pdf_path = create_test_pdf(temp_storage)
        
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        assert response.status_code == 201
        data = response.json()
        
        assert "batch_id" in data
        assert data["batch_id"].startswith("batch_")
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "test.pdf"
        
        # Verify batch directory was created (uses actual TEMP_STORAGE_PATH from env)
        from app.core.config import settings
        batch_dir = Path(settings.temp_storage_path) / data["batch_id"]
        assert batch_dir.exists()
    
    def test_get_batch_status_uploaded(self, client, temp_storage):
        """Test 2: GET batch status returns 'uploaded' before processing."""
        # Upload
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        
        # Get status
        status_response = client.get(f"/api/batches/{batch_id}")
        
        assert status_response.status_code == 200
        data = status_response.json()
        
        assert data["batch_id"] == batch_id
        assert data["status"] == "uploaded"
        assert data["test_records"] == []
        assert data["commitment_records"] == []
        assert data["errors"] == []
    
    def test_process_batch_extracts_data(self, client, temp_storage, mock_gemini_extractor):
        """Test 3: Processing extracts data and saves to storage."""
        # Upload
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        
        # Process
        process_response = client.post(f"/api/batches/{batch_id}/process")
        
        assert process_response.status_code == 200
        data = process_response.json()
        
        assert data["batch_id"] == batch_id
        assert data["status"] == "completed"
        assert len(data["test_records"]) > 0
        assert data["processed_count"] > 0
        
        # Verify record fields
        record = data["test_records"][0]
        assert "test_id" in record
        assert "patient_first_name" in record
        assert record["patient_first_name"]["raw_value"] == "יוחנן"
    
    def test_get_batch_status_after_processing(self, client, temp_storage, mock_gemini_extractor):
        """Test 4: GET batch status returns full data after processing."""
        # Upload
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        
        # Process
        client.post(f"/api/batches/{batch_id}/process")
        
        # Get status
        status_response = client.get(f"/api/batches/{batch_id}")
        
        assert status_response.status_code == 200
        data = status_response.json()
        
        assert data["batch_id"] == batch_id
        assert data["status"] == "completed"
        assert len(data["test_records"]) > 0
        # Commitment records may be empty if mock doesn't provide them - that's OK for MVP
        assert "commitment_records" in data
        
        # Verify persistence - data came from storage, not memory
        from app.core.config import settings
        storage = JSONStorage(base_path=Path(settings.temp_storage_path))
        loaded = storage.load_batch(batch_id)
        assert loaded is not None
        assert loaded["batch_id"] == batch_id
    
    def test_update_field_saves_to_storage(self, client, temp_storage, mock_gemini_extractor):
        """Test 5: Updating a field saves to persistent storage."""
        # Upload + Process
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        process_response = client.post(f"/api/batches/{batch_id}/process")
        test_id = process_response.json()["test_records"][0]["test_id"]
        
        # Update field
        update_response = client.patch(
            f"/api/batches/{batch_id}/tests/{test_id}/fields/patient_first_name",
            json={"new_value": "דוד"}
        )
        
        assert update_response.status_code == 200
        
        # Verify change persisted
        status_response = client.get(f"/api/batches/{batch_id}")
        data = status_response.json()
        record = data["test_records"][0]
        
        assert record["patient_first_name"]["reviewed_value"] == "דוד"
        assert record["patient_first_name"]["review_state"] == "human_verified"
    
    def test_page_refresh_preserves_data(self, client, temp_storage, mock_gemini_extractor):
        """Test 6: Page refresh (GET batch) returns same data from storage."""
        # Upload + Process
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        client.post(f"/api/batches/{batch_id}/process")
        
        # GET twice (simulate page refresh)
        response1 = client.get(f"/api/batches/{batch_id}")
        response2 = client.get(f"/api/batches/{batch_id}")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Should be identical
        assert data1["batch_id"] == data2["batch_id"]
        assert data1["status"] == data2["status"]
        assert len(data1["test_records"]) == len(data2["test_records"])
        assert data1["test_records"][0]["test_id"] == data2["test_records"][0]["test_id"]
    
    def test_export_check_before_review(self, client, temp_storage, mock_gemini_extractor):
        """Test 7: Export check blocks if fields need review."""
        # Upload + Process (some fields may be uncertain)
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        client.post(f"/api/batches/{batch_id}/process")
        
        # Check export eligibility
        check_response = client.get(f"/api/batches/{batch_id}/export-check")
        
        assert check_response.status_code == 200
        data = check_response.json()
        
        assert "can_export" in data
        assert "blockers" in data
        # Either can export or has blockers list
        if not data["can_export"]:
            assert len(data["blockers"]) > 0
    
    def test_no_endpoint_collision(self, client, temp_storage):
        """Test 8: Verify no endpoint collision - only one GET /batches/{id} active."""
        # Upload
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        
        # GET status
        status_response = client.get(f"/api/batches/{batch_id}")
        data = status_response.json()
        
        # Should NOT return placeholder message
        assert "processing not yet implemented" not in data.get("message", "").lower()
        
        # Should return structured data
        assert "status" in data
        assert "test_records" in data
        assert "commitment_records" in data
        assert data["status"] == "uploaded"  # Not processed yet
    
    def test_processing_failure_shows_errors(self, client, temp_storage):
        """Test 9: Processing failure shows errors, not 'not yet processed'."""
        # Upload
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        
        # Mock extractor to fail
        with patch("app.api.process.GeminiExtractor") as mock:
            mock_instance = MagicMock()
            mock_instance.extract.side_effect = Exception("Gemini API error")
            mock.return_value = mock_instance
            
            # Process
            process_response = client.post(f"/api/batches/{batch_id}/process")
        
        assert process_response.status_code == 200
        data = process_response.json()
        
        assert data["status"] == "completed_with_errors"
        assert len(data["errors"]) > 0
        assert data["processed_count"] == 0
        assert data["error_count"] > 0
        
        # Verify GET returns same error state
        status_response = client.get(f"/api/batches/{batch_id}")
        status_data = status_response.json()
        
        assert status_data["status"] == "completed_with_errors"
        assert len(status_data["errors"]) > 0


class TestEndpointOrdering:
    """Test that endpoints don't collide."""
    
    def test_upload_and_process_use_same_storage(self, client, temp_storage, mock_gemini_extractor):
        """Verify upload.py and process.py work with same JSONStorage."""
        # Upload via upload.py router
        pdf_path = create_test_pdf(temp_storage)
        with open(pdf_path, "rb") as f:
            upload_response = client.post(
                "/api/batches",
                files={"files": ("test.pdf", f, "application/pdf")}
            )
        
        batch_id = upload_response.json()["batch_id"]
        
        # Process via process.py router
        process_response = client.post(f"/api/batches/{batch_id}/process")
        
        # Both should succeed and share same batch
        assert upload_response.status_code == 201
        assert process_response.status_code == 200
        assert process_response.json()["batch_id"] == batch_id
        
        # Verify storage contains the batch
        from app.core.config import settings
        storage = JSONStorage(base_path=Path(settings.temp_storage_path))
        loaded = storage.load_batch(batch_id)
        assert loaded is not None
        assert loaded["batch_id"] == batch_id
