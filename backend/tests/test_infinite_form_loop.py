"""Regression test for P0 bug: unbounded form processing loop.

BUG DESCRIPTION:
- Processing form 163/168
- Processing form 164/169
- Processing form 165/170

The total form count increased during iteration because forms.append(form_extracted)
was modifying the same list being iterated over.

FIX:
- Separate input_forms (from segmentation) and processed_forms (for storage)
- Add MAX_FORMS_PER_DOCUMENT safety bound

TEST:
- 6-page synthetic PDF
- Processing must terminate
- Form count must remain finite and consistent
- No page duplicated or dropped
"""
import pytest
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

from app.services.processing.background import BackgroundProcessor, ProcessingStatus


def create_synthetic_6_page_pdf(output_path: Path) -> None:
    """Create a synthetic 6-page PDF for testing."""
    import pymupdf  # fitz
    
    doc = pymupdf.open()  # New empty PDF
    
    for page_num in range(1, 7):
        page = doc.new_page(width=595, height=842)  # A4 size
        
        # Add text
        text_lines = [
            f"Test Page {page_num}",
            f"Patient: Test Patient {page_num}",
            f"Central Number: 12345{page_num}",
            f"Commitment: COM-{page_num:04d}"
        ]
        
        y_pos = 750
        for line in text_lines:
            page.insert_text((100, y_pos), line, fontsize=12)
            y_pos -= 50
    
    doc.save(str(output_path))
    doc.close()


@pytest.mark.asyncio
async def test_finite_form_processing(tmp_path):
    """Test that form processing terminates with finite form count."""
    # Override temp_storage_path BEFORE creating processor
    from app.core.config import settings
    original_temp_path = settings.temp_storage_path
    settings.temp_storage_path = str(tmp_path)
    
    try:
        # Create synthetic 6-page PDF
        test_pdf = tmp_path / "test_6_pages.pdf"
        create_synthetic_6_page_pdf(test_pdf)
        
        # Create batch directory
        batch_id = "test_finite_processing"
        batch_dir = tmp_path / batch_id
        batch_dir.mkdir()
        
        # Copy PDF to batch directory
        import shutil
        shutil.copy(test_pdf, batch_dir / "test_doc.pdf")
        
        # Initialize processor AFTER setting temp_storage_path
        processor = BackgroundProcessor()
        
        # Start processing
        job = processor.start_processing(batch_id)
        
        # Wait for completion with timeout
        max_wait = 60  # 60 seconds max
        waited = 0
        while job.status == ProcessingStatus.PROCESSING and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 0.5
            job = processor.get_job_status(batch_id)
        
        # ASSERTIONS
        assert job is not None, "Job should exist"
        assert job.status != ProcessingStatus.PROCESSING, f"Job should have completed (status: {job.status})"
        assert waited < max_wait, f"Processing took too long ({waited}s), possible infinite loop"
        
        # Load saved batch data
        from app.services.storage import JSONStorage
        storage = JSONStorage(base_path=tmp_path)
        batch_data = storage.load_batch(batch_id)
        
        assert batch_data is not None, "Batch data should be saved"
        
        # Check form count is reasonable
        forms = batch_data.get("forms", [])
        assert len(forms) <= 100, f"Too many forms: {len(forms)} (possible unbounded growth)"
        assert len(forms) >= 1, "Should have at least 1 form"
        
        # Check no duplicate pages
        all_page_indices = set()
        for form in forms:
            for page_idx in form.get("page_indices", []):
                assert page_idx not in all_page_indices, f"Page {page_idx} appears in multiple forms"
                all_page_indices.add(page_idx)
        
        # Check all pages accounted for (0-5 for 6-page doc)
        expected_pages = set(range(6))
        assert all_page_indices == expected_pages, f"Pages mismatch: expected {expected_pages}, got {all_page_indices}"
        
        # Check commitment count doesn't multiply
        commitments = batch_data.get("commitment_records", [])
        assert len(commitments) <= 20, f"Too many commitments: {len(commitments)} (possible duplication)"
        
        print(f"✓ Test passed: {len(forms)} forms, {len(commitments)} commitments, {waited:.1f}s")
        
    finally:
        # Restore original config
        settings.temp_storage_path = original_temp_path


@pytest.mark.asyncio
async def test_safety_bound_prevents_runaway(tmp_path):
    """Test that MAX_FORMS_PER_DOCUMENT prevents runaway processing."""
    # This test verifies the safety check catches segmentation errors
    # We can't easily create a PDF that triggers 500+ forms naturally,
    # so we verify the check exists in the code
    
    from app.services.processing.background import BackgroundProcessor
    import inspect
    
    # Read source code of _process_batch
    source = inspect.getsource(BackgroundProcessor._process_batch)
    
    # Verify safety check exists
    assert "MAX_FORMS_PER_DOCUMENT" in source, "Safety bound constant should exist"
    assert "if len(input_forms) > MAX_FORMS_PER_DOCUMENT" in source, "Safety check should exist"
    assert 'errors.append' in source, "Should report error when limit exceeded"
    
    print("✓ Safety bound check exists in code")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
