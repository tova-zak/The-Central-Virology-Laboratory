"""
Create a NEW test batch to verify MockExtractor works end-to-end.
Monitors backend logs to confirm MockExtractor is invoked.
"""
import requests
import time
from PIL import Image
from io import BytesIO
import fitz

BASE_URL = "http://localhost:8000"

def create_test_pdf():
    """Create minimal synthetic PDF."""
    img = Image.new('RGB', (800, 1100), color='white')
    img_bytes = BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    doc = fitz.open()
    page = doc.new_page(width=800, height=1100)
    page.insert_image(page.rect, stream=img_bytes.getvalue())
    
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

print("="*70)
print("CREATING NEW MOCK TEST BATCH")
print("="*70)

# Create and upload
pdf_bytes = create_test_pdf()
files = {"files": ("mock_test.pdf", pdf_bytes, "application/pdf")}

print("\n[1/4] Uploading PDF...")
upload_resp = requests.post(f"{BASE_URL}/api/batches", files=files)
print(f"  Upload status: {upload_resp.status_code}")
assert upload_resp.status_code == 201

batch_data = upload_resp.json()
batch_id = batch_data["batch_id"]
document_id = batch_data["documents"][0]["document_id"]

print(f"  ✓ Created batch: {batch_id}")
print(f"  ✓ Document: {document_id}")

# Process
print(f"\n[2/4] Triggering processing...")
process_resp = requests.post(f"{BASE_URL}/api/batches/{batch_id}/process")
print(f"  Process status: {process_resp.status_code}")
assert process_resp.status_code == 202

# Wait and monitor
print(f"\n[3/4] Waiting for completion (check backend logs for MockExtractor)...")
for i in range(30):
    time.sleep(1)
    status_resp = requests.get(f"{BASE_URL}/api/batches/{batch_id}")
    batch = status_resp.json()
    status = batch["status"]
    
    print(f"  [{i+1}/30] Status: {status}", end="\r")
    
    if status in ["completed", "failed"]:
        break

print("\n")

# Get final results
status_resp = requests.get(f"{BASE_URL}/api/batches/{batch_id}")
batch = status_resp.json()

print(f"[4/4] FINAL RESULTS")
print(f"="*70)
print(f"Batch ID: {batch_id}")
print(f"Status: {batch['status']}")
print(f"Processed: {batch.get('processed_count', 0)}")
print(f"Errors: {batch.get('error_count', 0)}")

if batch['status'] == 'failed':
    print(f"\n❌ FAILED - Errors:")
    for err in batch.get('errors', []):
        print(f"  - Page {err['page_index']}: {err['error']}")
else:
    forms = batch.get('forms', [])
    commitments = batch.get('commitment_records', [])
    samples = batch.get('samples', [])
    
    print(f"\n✓ SUCCESS:")
    print(f"  Forms: {len(forms)}")
    print(f"  Commitment Records: {len(commitments)}")
    print(f"  Samples: {len(samples)}")
    
    if forms:
        form = forms[0]
        print(f"\n  First Form:")
        print(f"    - form_id: {form.get('form_id')}")
        print(f"    - patient: {form.get('patient_first_name', {}).get('raw_value')} {form.get('patient_last_name', {}).get('raw_value')}")
        print(f"    - sender: {form.get('sender', {}).get('raw_value')}")
    
    if commitments:
        comm = commitments[0]
        print(f"\n  First Commitment:")
        print(f"    - commitment_record_id: {comm.get('commitment_record_id')}")
        print(f"    - commitment_number: {comm.get('commitment_number')}")
        print(f"    - relationship_status: {comm.get('relationship_status')}")
        print(f"    - review_status: {comm.get('review_status')}")

print(f"\n{'='*70}")
print(f"Test batch ID for UI verification: {batch_id}")
print(f"Open UI: http://localhost:5173")
print(f"{'='*70}\n")
