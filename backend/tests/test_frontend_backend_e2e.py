"""End-to-end test: Frontend API client to Backend."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test /health endpoint (used by Frontend on startup)."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data
    assert "model" in data


def test_upload_flow_success():
    """Test complete upload flow as Frontend would use it."""
    from io import BytesIO
    
    # Create test PNG
    png_header = b'\x89PNG\r\n\x1a\n'
    content = png_header + b'\x00' * 100
    
    file_content = BytesIO(content)
    
    # Upload
    response = client.post(
        "/api/batches",
        files={"files": ("test.png", file_content, "image/png")}
    )
    
    assert response.status_code == 201
    data = response.json()
    
    # Verify response structure matches Frontend expectations
    assert "batch_id" in data
    assert "documents" in data
    assert isinstance(data["documents"], list)
    assert len(data["documents"]) > 0
    
    doc = data["documents"][0]
    assert "document_id" in doc
    assert "filename" in doc
    assert "size_bytes" in doc
    assert doc["filename"] == "test.png"


def test_batch_status_after_upload():
    """Test getting batch status after upload."""
    from io import BytesIO
    
    # Upload file
    png_content = BytesIO(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
    upload_response = client.post(
        "/api/batches",
        files={"files": ("status_test.png", png_content, "image/png")}
    )
    
    assert upload_response.status_code == 201
    batch_id = upload_response.json()["batch_id"]
    
    # Get status
    status_response = client.get(f"/api/batches/{batch_id}")
    
    assert status_response.status_code == 200
    status_data = status_response.json()
    assert status_data["batch_id"] == batch_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
