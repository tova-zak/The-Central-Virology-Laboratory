"""Final End-to-End Test: 3-page PDF → 3 commitment records"""
import os
import sys
import time
import requests
from pathlib import Path

os.environ["DEMO_MODE"] = "true"

API_URL = "http://localhost:8000"

def create_3_page_pdf():
    """Create 3-page synthetic PDF."""
    import pymupdf
    
    pdf_path = Path("test_3_pages_final.pdf")
    doc = pymupdf.open()
    
    for page_num in range(1, 4):
        page = doc.new_page(width=595, height=842)
        text_lines = [
            f"התחייבות עמוד {page_num}",
            f"שם מלא: דני כהן {page_num}",
            f"ת.ז: 12345678{page_num}",
            f"מספר מרכזי: 98765{page_num}",
            f"מספר התחייבות: 2024{page_num:04d}",
            f"תאריך קבלה: 2024-10-{page_num:02d}"
        ]
        
        y_pos = 750
        for line in text_lines:
            page.insert_text((100, y_pos), line, fontsize=14)
            y_pos -= 50
    
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path

def main():
    print("=" * 80)
    print("FINAL E2E TEST: 3-PAGE PDF → 3 COMMITMENT RECORDS")
    print("=" * 80)
    
    # Create 3-page PDF
    print("\n[1] Creating 3-page PDF...")
    pdf_path = create_3_page_pdf()
    print(f"✓ Created: {pdf_path}")
    
    # Upload
    print("\n[2] Uploading batch...")
    with open(pdf_path, 'rb') as f:
        files = {'files': (pdf_path.name, f, 'application/pdf')}
        response = requests.post(f"{API_URL}/api/batches", files=files, timeout=10)
        response.raise_for_status()
        data = response.json()
        batch_id = data['batch_id']
        print(f"✓ Batch uploaded: {batch_id}")
    
    # Start processing
    print("\n[3] Starting processing...")
    response = requests.post(f"{API_URL}/api/batches/{batch_id}/process", timeout=10)
    response.raise_for_status()
    print("✓ Processing started")
    
    # Poll
    print("\n[4] Waiting for completion...")
    for i in range(60):
        time.sleep(1)
        response = requests.get(f"{API_URL}/api/batches/{batch_id}", timeout=5)
        response.raise_for_status()
        batch_data = response.json()
        status = batch_data.get('status')
        
        if status in ['completed', 'completed_with_errors', 'failed']:
            print(f"\n✓ Processing finished: {status}")
            
            # VERIFY
            print("\n" + "=" * 80)
            print("VERIFICATION")
            print("=" * 80)
            
            commitment_records = batch_data.get('commitment_records', [])
            print(f"Batch ID: {batch_id}")
            print(f"Status: {status}")
            print(f"Commitment records: {len(commitment_records)}")
            
            if len(commitment_records) == 3:
                print("✅ PASS: Exactly 3 commitment records")
            else:
                print(f"❌ FAIL: Expected 3, got {len(commitment_records)}")
                return
            
            if status == 'completed':
                print("✅ PASS: status=completed")
            else:
                print(f"⚠ WARN: status={status}")
            
            # Check each commitment
            for idx, c in enumerate(commitment_records, 1):
                cid = c.get('commitment_record_id')
                cnum = c.get('commitment_number', {}).get('raw_value')
                print(f"\nCommitment {idx}:")
                print(f"  ID: {cid}")
                print(f"  Number: {cnum}")
                print(f"  Page index: {c.get('page_index', 'N/A')}")
            
            print("\n✅ TEST PASSED: 3-page PDF → 3 commitment records")
            
            # Cleanup
            pdf_path.unlink()
            return
    
    print("\n❌ FAIL: Timeout")
    pdf_path.unlink()

if __name__ == "__main__":
    main()
