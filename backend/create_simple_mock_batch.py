"""Create a SIMPLE mock batch with just 3 pages for fast testing."""
import os
import sys
from pathlib import Path
import requests
import time

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Set DEMO_MODE before importing anything
os.environ["DEMO_MODE"] = "true"

API_URL = "http://localhost:8000"

def create_simple_test_batch():
    """Create a test batch with a small 3-page PDF."""
    
    # Use one of the reference PDFs (first 3 pages only)
    ref_dir = backend_dir.parent.parent.parent / "reference"
    test_file = ref_dir / "התחייבויות - דוגמאות, חלק 1 (PDF).pdf"
    
    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return
    
    print(f"✓ Using test file: {test_file.name}")
    print(f"✓ DEMO_MODE: {os.getenv('DEMO_MODE')}")
    
    # Upload batch
    print("\n[1] Uploading batch...")
    with open(test_file, 'rb') as f:
        # Read only first 100KB to limit pages
        partial_content = f.read(100 * 1024)
    
    files = {'files': (test_file.name, partial_content, 'application/pdf')}
    
    try:
        response = requests.post(f"{API_URL}/api/upload", files=files, timeout=10)
        response.raise_for_status()
        data = response.json()
        batch_id = data['batch_id']
        print(f"✓ Batch uploaded: {batch_id}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return
    
    # Start processing
    print("\n[2] Starting processing...")
    try:
        response = requests.post(f"{API_URL}/api/process/{batch_id}", timeout=10)
        response.raise_for_status()
        print("✓ Processing started")
    except Exception as e:
        print(f"❌ Start processing failed: {e}")
        return
    
    # Wait for completion (max 60s)
    print("\n[3] Waiting for completion...")
    for i in range(60):
        time.sleep(1)
        try:
            response = requests.get(f"{API_URL}/api/batches/{batch_id}", timeout=5)
            response.raise_for_status()
            batch_data = response.json()
            status = batch_data.get('status')
            
            if status in ['completed', 'completed_with_errors', 'failed']:
                print(f"\n✓ Processing finished: {status}")
                print(f"\n📊 RESULTS:")
                print(f"   Batch ID: {batch_id}")
                print(f"   Status: {status}")
                print(f"   Processed: {batch_data.get('processed_count', 0)}")
                print(f"   Errors: {batch_data.get('error_count', 0)}")
                print(f"   Test records: {len(batch_data.get('test_records', []))}")
                print(f"   Commitment records: {len(batch_data.get('commitment_records', []))}")
                
                if batch_data.get('errors'):
                    print(f"\n⚠ Errors:")
                    for err in batch_data['errors'][:3]:
                        print(f"   - {err.get('error', err)}")
                
                return
        except Exception as e:
            print(f".", end="", flush=True)
            continue
    
    print(f"\n❌ Timeout waiting for batch completion")

if __name__ == "__main__":
    create_simple_test_batch()
