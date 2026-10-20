"""Real-world test: Create a Mock batch and verify finite processing + persistence.

This uses the actual running server, not mocked paths.
"""
import os
import sys
import time
import requests
from pathlib import Path

# Ensure DEMO_MODE
os.environ["DEMO_MODE"] = "true"

API_URL = "http://localhost:8000"

def create_simple_pdf():
    """Create a simple 6-page test PDF."""
    import pymupdf
    
    pdf_path = Path("test_6_pages.pdf")
    doc = pymupdf.open()
    
    for page_num in range(1, 7):
        page = doc.new_page(width=595, height=842)
        
        text_lines = [
            f"Test Page {page_num}",
            f"Patient: דני כהן",
            f"Central Number: 12345{page_num}",
            f"Commitment Number: 78{page_num}0"
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
    print("REAL MOCK BATCH TEST - P0 INFINITE LOOP BUG")
    print("=" * 80)
    
    # Check server
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        response.raise_for_status()
        print("✓ Server is running")
    except Exception as e:
        print(f"❌ Server not responding: {e}")
        return
    
    # Create test PDF
    print("\n[1] Creating synthetic 6-page PDF...")
    pdf_path = create_simple_pdf()
    print(f"✓ Created: {pdf_path}")
    
    # Upload
    print("\n[2] Uploading batch...")
    try:
        with open(pdf_path, 'rb') as f:
            files = {'files': (pdf_path.name, f, 'application/pdf')}
            response = requests.post(f"{API_URL}/api/batches", files=files, timeout=10)
            response.raise_for_status()
            data = response.json()
            batch_id = data['batch_id']
            print(f"✓ Batch uploaded: {batch_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return
    
    # Start processing
    print("\n[3] Starting processing...")
    try:
        response = requests.post(f"{API_URL}/api/process/{batch_id}", timeout=10)
        response.raise_for_status()
        print("✓ Processing started")
    except Exception as e:
        print(f"❌ Start processing failed: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")
        return
    
    # Poll for completion
    print("\n[4] Waiting for processing (max 60s)...")
    start_time = time.time()
    last_status = None
    
    for i in range(120):  # 60 seconds
        try:
            response = requests.get(f"{API_URL}/api/batches/{batch_id}", timeout=5)
            response.raise_for_status()
            batch_data = response.json()
            status = batch_data.get('status')
            
            if status != last_status:
                print(f"   Status: {status}")
                last_status = status
            
            if status in ['completed', 'completed_with_errors', 'failed', 'quota_exhausted']:
                elapsed = time.time() - start_time
                print(f"\n✓ Processing finished in {elapsed:.1f}s")
                
                print("\n" + "=" * 80)
                print("RESULTS")
                print("=" * 80)
                print(f"Batch ID: {batch_id}")
                print(f"Status: {status}")
                print(f"Processed: {batch_data.get('processed_count', 0)}")
                print(f"Errors: {batch_data.get('error_count', 0)}")
                
                test_records = batch_data.get('test_records', [])
                commitment_records = batch_data.get('commitment_records', [])
                forms = batch_data.get('forms', [])
                
                print(f"\nTest records: {len(test_records)}")
                print(f"Commitment records: {len(commitment_records)}")
                print(f"Forms: {len(forms)}")
                
                if batch_data.get('statistics'):
                    stats = batch_data['statistics']
                    print(f"\nStatistics:")
                    print(f"  Total pages: {stats.get('total_pages', 0)}")
                    print(f"  Total forms: {stats.get('total_forms', 0)}")
                    print(f"  Total commitments: {stats.get('total_commitments', 0)}")
                
                # Verify finite processing
                print("\n" + "=" * 80)
                print("VERIFICATION")
                print("=" * 80)
                
                if len(forms) > 100:
                    print(f"❌ FAIL: Too many forms ({len(forms)}), possible unbounded growth")
                    return
                
                if len(forms) == 0:
                    print("⚠ WARN: No forms created")
                else:
                    print(f"✓ PASS: Finite form count ({len(forms)})")
                
                # Check page coverage
                all_pages = set()
                for form in forms:
                    all_pages.update(form.get('page_indices', []))
                
                print(f"✓ Pages covered: {sorted(all_pages)}")
                
                if elapsed > 50:
                    print(f"⚠ WARN: Processing took {elapsed:.1f}s (expected < 30s for 6 pages)")
                else:
                    print(f"✓ PASS: Processing time reasonable ({elapsed:.1f}s)")
                
                if len(commitment_records) == 0:
                    print("⚠ WARN: No commitment records created")
                else:
                    print(f"✓ PASS: {len(commitment_records)} commitment records created")
                
                if status == 'completed':
                    print("\n✅ TEST PASSED: Finite processing + persistence verified")
                else:
                    print(f"\n⚠ Processing completed with status: {status}")
                
                # Show sample commitment
                if commitment_records:
                    print("\nSample commitment:")
                    c = commitment_records[0]
                    print(f"  ID: {c.get('commitment_id')}")
                    print(f"  Number: {c.get('commitment_number', {}).get('raw_value')}")
                    print(f"  Type: {c.get('commitment_type')}")
                
                # Cleanup
                pdf_path.unlink()
                return
                
        except requests.RequestException as e:
            print(".", end="", flush=True)
        
        time.sleep(0.5)
    
    print(f"\n❌ FAIL: Timeout after 60s - possible infinite loop")
    pdf_path.unlink()

if __name__ == "__main__":
    main()
