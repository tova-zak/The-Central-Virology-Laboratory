"""Tests for document viewing endpoint."""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


client = TestClient(app)


@pytest.fixture
def temp_batch(tmp_path):
    """Create a temporary batch with test documents."""
    batch_id = "test_batch_doc"
    batch_dir = tmp_path / batch_id
    batch_dir.mkdir()
    
    # Create test PDF
    pdf_path = batch_dir / "doc_001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ntest content")
    
    # Create test image
    png_path = batch_dir / "doc_002.png"
    png_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fake png data")
    
    # Save original temp_storage_path
    original_path = settings.temp_storage_path
    settings.temp_storage_path = str(tmp_path)
    
    yield batch_id, batch_dir
    
    # Restore
    settings.temp_storage_path = original_path


def test_get_pdf_document(temp_batch):
    """Test successful PDF retrieval."""
    batch_id, batch_dir = temp_batch
    
    response = client.get(f"/api/batches/{batch_id}/documents/doc_001")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert b"%PDF" in response.content


def test_get_image_document(temp_batch):
    """Test successful image retrieval."""
    batch_id, batch_dir = temp_batch
    
    response = client.get(f"/api/batches/{batch_id}/documents/doc_002")
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert b"PNG" in response.content


def test_document_not_found(temp_batch):
    """Test 404 when document doesn't exist."""
    batch_id, _ = temp_batch
    
    response = client.get(f"/api/batches/{batch_id}/documents/nonexistent")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_batch_not_found(temp_batch):
    """Test 404 when batch doesn't exist."""
    _, _ = temp_batch
    
    response = client.get("/api/batches/nonexistent_batch/documents/doc_001")
    
    assert response.status_code == 404
    assert "batch" in response.json()["detail"].lower()


def test_path_traversal_blocked(temp_batch):
    """Test path traversal attempts are blocked."""
    batch_id, _ = temp_batch
    
    # Try various path traversal patterns
    # These will fail regex validation (slashes, dots, special chars)
    traversal_patterns = [
        "../secret",
        "..%2F..%2Fsecret",
        "....//....//secret",
    ]
    
    for pattern in traversal_patterns:
        response = client.get(f"/api/batches/{batch_id}/documents/{pattern}")
        # Either 400 (bad format) or 404 (not found after validation) is acceptable
        # Both mean the traversal was blocked
        assert response.status_code in [400, 404], f"Pattern {pattern} should be blocked"


def test_invalid_batch_id(temp_batch):
    """Test invalid batch ID format is rejected."""
    _, _ = temp_batch
    
    response = client.get("/api/batches/../../etc/passwd/documents/doc_001")
    
    # 404 is acceptable here - the path contains invalid chars and doesn't exist
    assert response.status_code in [400, 404]


def test_invalid_document_id(temp_batch):
    """Test invalid document ID format is rejected."""
    batch_id, _ = temp_batch
    
    response = client.get(f"/api/batches/{batch_id}/documents/../../secret")
    
    # 404 is acceptable here - the traversal pattern doesn't match a real file
    assert response.status_code in [400, 404]
