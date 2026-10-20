"""Integration test for processing API - no mocks, real flow."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from PIL import Image
from io import BytesIO

from app.main import app
from app.core import config


client = TestClient(app)


@pytest.fixture
def temp_batch_with_image(tmp_path, monkeypatch):
    """Create a temporary batch with a real test image."""
    # Mock settings to use tmp_path
    monkeypatch.setattr(config.settings, 'temp_storage_path', str(tmp_path))
    
    batch_id = "integration_test_batch"
    batch_dir = tmp_path / batch_id
    batch_dir.mkdir()
    
    # Create a simple test image
    img = Image.new('RGB', (800, 600), color='white')
    img_path = batch_dir / "doc_001.png"
    img.save(img_path)
    
    return batch_id, batch_dir


def test_process_empty_batch(tmp_path, monkeypatch):
    """Test processing batch with no files returns 400."""
    monkeypatch.setattr(config.settings, 'temp_storage_path', str(tmp_path))
    
    batch_id = "empty_batch"
    batch_dir = tmp_path / batch_id
    batch_dir.mkdir()
    
    response = client.post(f"/api/batches/{batch_id}/process")
    
    assert response.status_code == 400
    assert "no files found" in response.json()["detail"].lower()


def test_get_uploaded_batch_status(temp_batch_with_image):
    """Test getting status of uploaded but not processed batch."""
    batch_id, _ = temp_batch_with_image
    
    response = client.get(f"/api/batches/{batch_id}")
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["batch_id"] == batch_id
    assert data["status"] == "uploaded"
    # Batch exists but not processed yet, should have empty arrays
    assert isinstance(data.get("test_records", []), list)
    assert isinstance(data.get("commitment_records", []), list)
