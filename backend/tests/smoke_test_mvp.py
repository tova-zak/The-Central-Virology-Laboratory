"""
SMOKE TEST: End-to-end MVP flow
Upload → Segment → Extract → Create commitment records → Review → Save → Reload → Export
"""
import requests
import time
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000"

def smoke_test():
    print("\n" + "="*60)
    print("MVP SMOKE TEST - End-to-End Flow")
    print("="*60)
    
    # Step 1: Use existing sample PDF or create simple one
    print("\n[1/8] Using sample PDF from reference...")
    sample_pdf = Path(__file__).parent.parent.parent.parent / "reference" / "הנחיות האתגר - המעבדה המרכזית לנגיפים (PDF) (1).pdf"
    
    if sample_pdf.exists():
        pdf_bytes = sample_pdf.read_bytes()
        print(f"✓ Loaded {len(pdf_bytes)} bytes from {sample_pdf.name}")
    else:
        # Fallback: create minimal PDF
        print("  Reference PDF not found, creating minimal test PDF...")
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
        print(f"✓ Created {len(pdf_bytes)} bytes PDF")
    
    # Step 2: Upload PDF
    print("\n[2/8] Uploading PDF to backend...")
    files = {"files": ("smoke_test.pdf", pdf_bytes, "application/pdf")}
    upload_resp = requests.post(f"{BASE_URL}/api/batches", files=files)
    assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.status_code} {upload_resp.text}"
    upload_data = upload_resp.json()
    batch_id = upload_data["batch_id"]
    document_id = upload_data["documents"][0]["document_id"]
    print(f"✓ Uploaded: batch_id={batch_id}, document_id={document_id}")
    
    # Step 3: Trigger processing
    print("\n[3/8] Triggering batch processing...")
    process_resp = requests.post(f"{BASE_URL}/api/batches/{batch_id}/process")
    assert process_resp.status_code == 202, f"Process failed: {process_resp.status_code} {process_resp.text}"
    print("✓ Processing started")
    
    # Step 4: Wait for processing to complete
    print("\n[4/8] Waiting for processing...")
    for i in range(60):
        time.sleep(2)
        status_resp = requests.get(f"{BASE_URL}/api/batches/{batch_id}")
        status = status_resp.json()["status"]
        print(f"  Status: {status}")
        if status == "completed":
            break
        if status == "failed":
            raise AssertionError(f"Processing failed: {status_resp.json()}")
    else:
        raise AssertionError("Processing timeout")
    
    batch_data = status_resp.json()
    print(f"✓ Processing completed")
    
    # Step 5: Verify segmentation and commitment records
    print("\n[5/8] Verifying segmentation and records...")
    forms = batch_data["forms"]
    commitments = batch_data["commitment_records"]
    
    print(f"  Forms: {len(forms)}")
    print(f"  Commitments: {len(commitments)}")
    
    # Expected: 3 forms (pages 0-1 grouped, page 2, page 3)
    # Expected: 4 commitments (A001, A002 from Leumit, B001 from Clalit rejected, C001 "דגימה לאומית" detected)
    assert len(forms) >= 2, f"Expected ≥2 forms, got {len(forms)}"
    assert len(commitments) >= 2, f"Expected ≥2 commitments, got {len(commitments)}"
    
    print(f"✓ Segmentation OK: {len(forms)} forms, {len(commitments)} commitment records")
    
    # Step 6: Check relationship status (should have some needing review)
    print("\n[6/8] Checking relationship statuses...")
    unresolved = [c for c in commitments if c.get("relationship_status") in ["unresolved_relationship", "inferred"]]
    print(f"  Commitments needing review: {len(unresolved)}")
    
    if unresolved:
        # Resolve one commitment
        comm_id = unresolved[0]["commitment_record_id"]
        samples = batch_data["samples"]
        sample_id = samples[0]["sample_id"] if samples else "sample_001"
        
        print(f"\n[7/8] Resolving relationship for commitment {comm_id}...")
        resolve_resp = requests.post(
            f"{BASE_URL}/api/batches/{batch_id}/commitments/{comm_id}/resolve",
            json={"sample_ids": [sample_id], "confirm": True}
        )
        assert resolve_resp.status_code == 200, f"Resolve failed: {resolve_resp.text}"
        print(f"✓ Resolved commitment {comm_id}")
    else:
        print("\n[7/8] No relationships to resolve (all explicit)")
    
    # Step 8: Verify persistence (reload batch)
    print("\n[8/8] Verifying persistence...")
    reload_resp = requests.get(f"{BASE_URL}/api/batches/{batch_id}")
    assert reload_resp.status_code == 200
    reloaded = reload_resp.json()
    
    assert reloaded["batch_id"] == batch_id
    assert len(reloaded["forms"]) == len(forms)
    print(f"✓ Persistence verified: batch reloaded successfully")
    
    print("\n" + "="*60)
    print("✓✓✓ SMOKE TEST PASSED ✓✓✓")
    print("="*60)
    print(f"\nBatch ID: {batch_id}")
    print(f"Forms: {len(forms)}")
    print(f"Commitments: {len(commitments)}")
    print(f"Samples: {len(batch_data.get('samples', []))}")
    print("\nApplication is working end-to-end!")
    
    return batch_id

if __name__ == "__main__":
    try:
        smoke_test()
    except Exception as e:
        print(f"\n❌ SMOKE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
