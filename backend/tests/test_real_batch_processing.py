"""
Real integration test for batch processing with Hybrid Engine.

Tests the ACTUAL backend path that the web server uses:
POST /api/batches/{batch_id}/process

This test verifies that ALL config instantiations work correctly
and that a full batch can be processed end-to-end.
"""
import io
import os
import pytest
import shutil
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Set test environment BEFORE any imports
os.environ['DEMO_MODE'] = 'true'  # Use mock Gemini
os.environ['HYBRID_ENGINE_ENABLED'] = 'true'
os.environ['HYBRID_ENABLE_PREPROCESSING'] = 'true'
os.environ['HYBRID_ENABLE_OCR'] = 'true'
os.environ['HYBRID_ENABLE_HYBRID_VERIFICATION'] = 'true'
os.environ['HYBRID_ENABLE_FOCUSED_RETRY'] = 'false'
os.environ['TESSERACT_CMD'] = 'D:\\Users\\1\\tesseract.exe'
os.environ['TEMP_STORAGE_PATH'] = 'd:\\temp\\test_batches'

from app.core.config import settings
from app.core.hybrid_config import get_hybrid_config, reset_hybrid_config
from app.services.processing.background import BackgroundProcessor, get_processor


def create_synthetic_png():
    """Create a synthetic PNG image for testing."""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40)
        font_normal = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
    except:
        font_large = font_normal = ImageFont.load_default()
    
    y = 50
    
    # Title
    draw.text((250, y), "טופס בדיקה סינתטי", fill='black', font=font_large)
    y += 80
    
    # Patient info
    draw.text((50, y), "שם פרטי: אבי", fill='black', font=font_normal)
    y += 60
    draw.text((50, y), "שם משפחה: לוי", fill='black', font=font_normal)
    y += 60
    draw.text((50, y), "ת.ז: 123456782", fill='black', font=font_normal)  # Valid Israeli ID
    y += 60
    
    # Institution
    draw.text((50, y), "מוסד: המעבדה המרכזית", fill='black', font=font_normal)
    y += 60
    
    # Date
    draw.text((50, y), "תאריך: 15/03/2024", fill='black', font=font_normal)
    y += 60
    
    # Numbers
    draw.text((50, y), "מספר מרכזי: 111222", fill='black', font=font_normal)
    y += 60
    draw.text((50, y), "מס' התחייבות: TEST001", fill='black', font=font_normal)
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


@pytest.fixture
def setup_batch_directory():
    """Create a test batch directory with a single PNG file."""
    batch_id = "test-batch-001"
    batch_dir = Path(settings.temp_storage_path) / batch_id
    
    # Clean up if exists
    if batch_dir.exists():
        shutil.rmtree(batch_dir)
    
    # Create directory
    batch_dir.mkdir(parents=True, exist_ok=True)
    
    # Create PNG file
    png_path = batch_dir / "test-form-001.png"
    png_bytes = create_synthetic_png()
    png_path.write_bytes(png_bytes)
    
    yield batch_id, batch_dir
    
    # Cleanup after test
    if batch_dir.exists():
        shutil.rmtree(batch_dir)


class TestRealBatchProcessing:
    """Test actual batch processing with BackgroundProcessor."""
    
    def setup_method(self):
        """Reset config before each test."""
        reset_hybrid_config()
    
    @pytest.mark.asyncio
    async def test_full_batch_processing_pipeline(self, setup_batch_directory):
        """
        Test COMPLETE batch processing pipeline with Hybrid Engine.
        
        This test simulates exactly what happens when:
        POST /api/batches/{batch_id}/process
        
        Steps:
        1. Create batch with PNG file
        2. Start processing
        3. PreprocessingConfig instantiation
        4. OCRConfig instantiation
        5. VerificationConfig instantiation
        6. Mock Gemini extraction
        7. Real OCR extraction (if Tesseract available)
        8. Hybrid verification
        9. Save TestRecord
        10. Complete batch
        """
        batch_id, batch_dir = setup_batch_directory
        
        print(f"\n{'='*70}")
        print(f"Testing Real Batch Processing")
        print(f"{'='*70}")
        print(f"Batch ID: {batch_id}")
        print(f"Batch Dir: {batch_dir}")
        print(f"Files: {list(batch_dir.glob('*'))}")
        print()
        
        # Get the real processor (same one used by the server)
        processor = get_processor()
        
        # Verify settings
        assert settings.demo_mode is True, "Demo mode must be enabled for this test"
        assert settings.temp_storage_path is not None
        
        # Step 1: Start processing (THIS IS THE REAL BACKEND PATH)
        print("Step 1: Starting batch processing...")
        job = processor.start_processing(batch_id)
        
        assert job is not None
        assert job.batch_id == batch_id
        print(f"✓ Job created: {job.batch_id}")
        
        # Step 2: Wait for processing to complete
        print("\nStep 2: Waiting for processing to complete...")
        max_wait = 30  # 30 seconds timeout
        elapsed = 0
        
        while elapsed < max_wait:
            await asyncio.sleep(0.5)
            elapsed += 0.5
            
            job_status = processor.get_job_status(batch_id)
            
            if job_status.status in ["completed", "failed", "completed_with_errors"]:
                break
        
        # Step 3: Check final status
        final_job = processor.get_job_status(batch_id)
        
        print(f"\n{'='*70}")
        print(f"Processing Complete")
        print(f"{'='*70}")
        print(f"Status: {final_job.status}")
        print(f"Progress: {final_job.progress}")
        print(f"Error: {final_job.error}")
        print()
        
        # Load results from storage
        from app.services.storage import JSONStorage
        storage = JSONStorage(base_path=Path(settings.temp_storage_path))
        
        try:
            batch_result = storage.load_batch(batch_id)
            
            print(f"Batch Results:")
            print(f"  Status: {batch_result['status']}")
            print(f"  Processed: {batch_result['processed_count']}")
            print(f"  Errors: {batch_result['error_count']}")
            print(f"  Test Records: {len(batch_result.get('test_records', []))}")
            print(f"  Commitment Records: {len(batch_result.get('commitment_records', []))}")
            
            if batch_result.get('errors'):
                print(f"\n  Errors:")
                for err in batch_result['errors']:
                    print(f"    - {err}")
            
            print(f"{'='*70}")
            
            # ASSERTIONS - These must ALL pass for the test to succeed
            
            # 1. Status must be completed (not failed)
            assert final_job.status == "completed", \
                f"Expected 'completed', got '{final_job.status}'. Error: {final_job.error}"
            
            # 2. Must have processed at least 1 record
            assert batch_result['processed_count'] >= 1, \
                f"Expected processed_count >= 1, got {batch_result['processed_count']}"
            
            # 3. Must have zero errors
            assert batch_result['error_count'] == 0, \
                f"Expected 0 errors, got {batch_result['error_count']}. Errors: {batch_result.get('errors')}"
            
            # 4. Must have at least one test record
            assert len(batch_result.get('test_records', [])) >= 1, \
                "Expected at least 1 test record"
            
            # 5. Test record must have valid structure
            test_record = batch_result['test_records'][0]
            assert 'fields' in test_record
            assert 'extraction_state' in test_record
            
            # 6. Verify no Gemini calls were made (demo mode)
            assert test_record.get('extraction_metadata', {}).get('model_id') in ['mock-demo', 'mock-extractor-v1'], \
                "Demo mode should use mock extractor"
            
            print("\n✅ ALL ASSERTIONS PASSED")
            print(f"{'='*70}")
            
        except FileNotFoundError:
            pytest.fail(f"Batch result file not found for {batch_id}")


@pytest.mark.asyncio
async def test_config_instantiation_in_real_processor():
    """Test that all Config classes can be instantiated by BackgroundProcessor."""
    
    # Reset config
    reset_hybrid_config()
    
    # Create processor (this will lazy-load configs)
    processor = BackgroundProcessor()
    
    # Force initialization of all configs
    try:
        # Preprocessing
        if processor._hybrid_config.enable_preprocessing:
            preprocessor = processor._get_preprocessor()
            assert preprocessor is not None
            print("✓ PreprocessingConfig instantiated successfully")
        
        # OCR
        if processor._hybrid_config.enable_ocr:
            ocr_extractor = processor._get_ocr_extractor()
            assert ocr_extractor is not None
            print("✓ OCRConfig instantiated successfully")
        
        # Verifier
        if processor._hybrid_config.enable_hybrid_verification:
            verifier = processor._get_hybrid_verifier()
            assert verifier is not None
            print("✓ VerificationConfig instantiated successfully")
        
        print("\n✅ All Config instantiations successful")
        
    except TypeError as e:
        pytest.fail(f"Config instantiation failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
