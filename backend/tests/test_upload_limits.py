"""Test file upload limits per D-14 requirements."""
import pytest
from io import BytesIO
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def create_fake_png(size_bytes: int) -> BytesIO:
    """Create a fake PNG file with valid magic bytes.
    
    Uses PNG header + minimal valid structure to pass magic byte check
    without creating actual large images.
    """
    # PNG signature
    png_header = b'\x89PNG\r\n\x1a\n'
    # IHDR chunk (minimal valid PNG)
    ihdr = b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    # IDAT chunk (minimal data)
    idat = b'\x00\x00\x00\x0cIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
    # IEND chunk
    iend = b'\x00\x00\x00\x00IEND\xaeB`\x82'
    
    base_content = png_header + ihdr + idat + iend
    
    # Pad to desired size if needed
    if size_bytes > len(base_content):
        # Add padding after IDAT, before IEND
        padding = b'\x00' * (size_bytes - len(base_content))
        content = png_header + ihdr + idat + padding + iend
    else:
        content = base_content
    
    return BytesIO(content)


def test_single_file_within_limit():
    """Test uploading a single file within 20MB limit."""
    # Create 1MB file (well within limit)
    file_content = create_fake_png(1024 * 1024)
    
    response = client.post(
        "/api/batches",
        files={"files": ("test.png", file_content, "image/png")}
    )
    
    assert response.status_code == 201
    assert "batch_id" in response.json()
    assert len(response.json()["documents"]) == 1


def test_single_file_exceeds_20mb_limit():
    """Test that a file exceeding 20MB is rejected."""
    # Create 21MB file (exceeds limit)
    file_size = 21 * 1024 * 1024
    file_content = create_fake_png(file_size)
    
    response = client.post(
        "/api/batches",
        files={"files": ("large.png", file_content, "image/png")}
    )
    
    assert response.status_code == 413  # Request Entity Too Large
    assert "too large" in response.json()["detail"].lower()
    assert "20" in response.json()["detail"]  # Should mention 20MB limit


def test_single_file_exactly_20mb():
    """Test edge case: file exactly at 20MB limit should succeed."""
    # Create exactly 20MB file
    file_size = 20 * 1024 * 1024
    file_content = create_fake_png(file_size)
    
    response = client.post(
        "/api/batches",
        files={"files": ("exact.png", file_content, "image/png")}
    )
    
    assert response.status_code == 201
    assert "batch_id" in response.json()


def test_batch_with_10_files():
    """Test uploading exactly 10 files (maximum per batch)."""
    files = []
    for i in range(10):
        file_content = create_fake_png(1024)  # 1KB each
        files.append(("files", (f"file{i}.png", file_content, "image/png")))
    
    response = client.post("/api/batches", files=files)
    
    assert response.status_code == 201
    assert len(response.json()["documents"]) == 10


def test_batch_with_11_files_rejected():
    """Test that uploading 11 files (exceeds limit) is rejected."""
    files = []
    for i in range(11):
        file_content = create_fake_png(1024)  # 1KB each
        files.append(("files", (f"file{i}.png", file_content, "image/png")))
    
    response = client.post("/api/batches", files=files)
    
    assert response.status_code == 400  # Bad Request
    assert "too many files" in response.json()["detail"].lower()
    assert "10" in response.json()["detail"]  # Should mention 10 file limit


def test_multiple_files_one_exceeds_limit():
    """Test that if one file in batch exceeds limit, request is rejected."""
    files = [
        ("files", ("small.png", create_fake_png(1024), "image/png")),
        ("files", ("large.png", create_fake_png(21 * 1024 * 1024), "image/png")),
    ]
    
    response = client.post("/api/batches", files=files)
    
    assert response.status_code == 413
    assert "large.png" in response.json()["detail"]


def test_empty_file_list():
    """Test that uploading zero files returns appropriate error."""
    response = client.post("/api/batches", files=[])
    
    # FastAPI should return 422 for missing required field
    assert response.status_code == 422


def test_file_with_invalid_mime_type():
    """Test that non-image files are rejected."""
    file_content = BytesIO(b"This is a text file")
    
    response = client.post(
        "/api/batches",
        files={"files": ("test.txt", file_content, "text/plain")}
    )
    
    assert response.status_code == 400
    assert "invalid file type" in response.json()["detail"].lower()


def test_file_with_mismatched_magic_bytes():
    """Test that files with content not matching MIME type are rejected."""
    # Text content but claiming to be PNG
    file_content = BytesIO(b"This is not a PNG file")
    
    response = client.post(
        "/api/batches",
        files={"files": ("fake.png", file_content, "image/png")}
    )
    
    assert response.status_code == 400
    assert "content does not match" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
