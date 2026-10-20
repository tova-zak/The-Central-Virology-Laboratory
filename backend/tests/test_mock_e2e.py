"""
E2E Test: Mock Mode Processing
Verifies that DEMO_MODE produces valid records for UI display.
"""
import os
import pytest
import requests
from pathlib import Path

# Set DEMO_MODE for this test
os.environ['DEMO_MODE'] = 'true'

BASE_URL = "http://localhost:8000"

def test_mock_mode_produces_valid_records():
    """Test that MockExtractor produces displayable records."""
    
    # Create minimal test PDF
    from PIL import Image
    from io import BytesIO
    import fitz
    
    img = Image.new('RGB', (800, 1100), color='white')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    doc = fitz.open()
    page = doc.new_page(width=800, height=1100)
    page.insert_image(page.rect, stream=img_bytes.getvalue())
    
    pdf_bytes = doc.write()
    doc.close()
    
    # Upload
    files = {"files": ("test.pdf", pdf_bytes, "application/pdf")}
    upload_resp = requests.post(f"{BASE_URL}/api/batches", files=files)
    assert upload_resp.status_code == 201
    
    batch_id = upload_resp.json()["batch_id"]
    
    # Process
    process_resp = requests.post(f"{BASE_URL}/api/batches/{batch_id}/process")
    assert process_resp.status_code == 202
    
    # Wait for completion
    import time
    for _ in range(30):
        time.sleep(1)
        status_resp = requests.get(f"{BASE_URL}/api/batches/{batch_id}")
        batch = status_resp.json()
        
        if batch["status"] == "completed":
            break
        elif batch["status"] == "failed":
            pytest.fail(f"Processing failed: {batch.get('errors', [])}")
    
    # Verify results
    assert batch["status"] == "completed", f"Status: {batch['status']}"
    
    # Must have at least one form
    assert "forms" in batch, "Missing 'forms' key"
    forms = batch.get("forms", [])
    assert len(forms) > 0, "No forms created - UI will show zero records"
    
    # Must have at least one commitment record
    assert "commitment_records" in batch, "Missing 'commitment_records' key"
    commitments = batch.get("commitment_records", [])
    assert len(commitments) > 0, "No commitments created - UI will show zero records"
    
    # Verify commitment structure
    first_commitment = commitments[0]
    assert "commitment_record_id" in first_commitment
    assert "commitment_number" in first_commitment
    assert "form_id" in first_commitment
    assert "relationship_status" in first_commitment
    assert "review_status" in first_commitment
    
    print(f"\n✓ Mock mode test passed:")
    print(f"  Forms: {len(forms)}")
    print(f"  Commitments: {len(commitments)}")
    print(f"  Samples: {len(batch.get('samples', []))}")
    
if __name__ == "__main__":
    test_mock_mode_produces_valid_records()
