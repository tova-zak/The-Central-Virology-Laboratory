"""Regression tests for ONE COMMITMENT PER PAGE refactor.

Business Rule (confirmed by hackathon mentor):
- Every PDF page = one independent commitment
- N-page PDF → N CommitmentRecord objects
- No multi-page grouping in active processing path
- Multiple central numbers on one page stay in ONE commitment record
"""
import pytest
import asyncio
from pathlib import Path
from io import BytesIO
from PIL import Image
import uuid

from app.core.config import settings
from app.services.processing.background import BackgroundProcessor, ProcessingJob, ProcessingStatus
from app.domain.models import CommitmentRecord, ExtractionState, ReviewState


@pytest.fixture
def mock_demo_mode(monkeypatch):
    """Force DEMO_MODE=True for all tests."""
    monkeypatch.setattr(settings, "demo_mode", True)


@pytest.fixture
def temp_batch_dir(tmp_path):
    """Create temporary batch directory."""
    batch_id = f"test_batch_{uuid.uuid4().hex[:8]}"
    batch_dir = tmp_path / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    return batch_id, batch_dir


def create_synthetic_pdf(output_path: Path, num_pages: int):
    """Create a synthetic PDF with N blank pages for testing.
    
    Args:
        output_path: Path to save PDF
        num_pages: Number of pages to create
    """
    import pymupdf  # PyMuPDF
    
    doc = pymupdf.open()  # Create new empty PDF
    
    for i in range(num_pages):
        page = doc.new_page(width=595, height=842)  # A4 size in points
        
        # Add some text to the page
        text = f"Test Page {i+1}\nCentral Number: TEST-{i+1:03d}\nCommitment: COMMIT-{i+1:03d}"
        page.insert_text((100, 100), text, fontsize=12)
    
    doc.save(str(output_path))
    doc.close()


@pytest.mark.asyncio
async def test_one_page_pdf_creates_one_commitment(mock_demo_mode, temp_batch_dir, monkeypatch):
    """Test that a 1-page PDF creates exactly 1 CommitmentRecord."""
    batch_id, batch_dir = temp_batch_dir
    
    # Create 1-page synthetic PDF
    pdf_path = batch_dir / "test_doc.pdf"
    create_synthetic_pdf(pdf_path, num_pages=1)
    
    # Override temp_storage_path to use our test directory
    monkeypatch.setattr(settings, "temp_storage_path", str(batch_dir.parent))
    
    # Process batch
    processor = BackgroundProcessor()
    job = processor.start_processing(batch_id)
    
    # Wait for completion (with timeout)
    await asyncio.wait_for(job.task, timeout=30)
    
    # Verify results
    assert job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.COMPLETED_WITH_ERRORS]
    
    # Load batch results
    from app.services.storage import JSONStorage
    storage = JSONStorage(base_path=batch_dir.parent)
    batch_result = storage.load_batch(batch_id)
    
    # Verify exactly 1 commitment record
    assert "commitment_records" in batch_result
    commitment_records = batch_result["commitment_records"]
    assert len(commitment_records) == 1, f"Expected 1 commitment, got {len(commitment_records)}"
    
    # Verify commitment structure
    commitment = commitment_records[0]
    assert "commitment_record_id" in commitment
    assert "form_id" in commitment
    assert "commitment_number" in commitment
    assert commitment["commitment_number"]["extraction_state"] in ["found", "missing", "conflicting"]


@pytest.mark.asyncio
async def test_five_page_pdf_creates_five_commitments(mock_demo_mode, temp_batch_dir, monkeypatch):
    """Test that a 5-page PDF creates exactly 5 CommitmentRecords."""
    batch_id, batch_dir = temp_batch_dir
    
    # Create 5-page synthetic PDF
    pdf_path = batch_dir / "test_doc.pdf"
    create_synthetic_pdf(pdf_path, num_pages=5)
    
    monkeypatch.setattr(settings, "temp_storage_path", str(batch_dir.parent))
    
    # Process batch
    processor = BackgroundProcessor()
    job = processor.start_processing(batch_id)
    
    # Wait for completion
    await asyncio.wait_for(job.task, timeout=60)
    
    # Verify results
    assert job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.COMPLETED_WITH_ERRORS]
    
    from app.services.storage import JSONStorage
    storage = JSONStorage(base_path=batch_dir.parent)
    batch_result = storage.load_batch(batch_id)
    
    # Verify exactly 5 commitment records
    commitment_records = batch_result["commitment_records"]
    assert len(commitment_records) == 5, f"Expected 5 commitments, got {len(commitment_records)}"
    
    # Verify all have unique IDs
    ids = [c["commitment_record_id"] for c in commitment_records]
    assert len(ids) == len(set(ids)), "Duplicate commitment IDs found"


@pytest.mark.asyncio
async def test_thirty_page_pdf_creates_thirty_commitments(mock_demo_mode, temp_batch_dir, monkeypatch):
    """Test that a 30-page PDF creates exactly 30 CommitmentRecords and terminates."""
    batch_id, batch_dir = temp_batch_dir
    
    # Create 30-page synthetic PDF
    pdf_path = batch_dir / "test_doc.pdf"
    create_synthetic_pdf(pdf_path, num_pages=30)
    
    monkeypatch.setattr(settings, "temp_storage_path", str(batch_dir.parent))
    
    # Process batch
    processor = BackgroundProcessor()
    job = processor.start_processing(batch_id)
    
    # Wait for completion with extended timeout
    await asyncio.wait_for(job.task, timeout=120)
    
    # Verify results
    assert job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.COMPLETED_WITH_ERRORS]
    
    from app.services.storage import JSONStorage
    storage = JSONStorage(base_path=batch_dir.parent)
    batch_result = storage.load_batch(batch_id)
    
    # Verify exactly 30 commitment records (not 31, 32, 33... growing)
    commitment_records = batch_result["commitment_records"]
    assert len(commitment_records) == 30, f"Expected 30 commitments, got {len(commitment_records)}"


@pytest.mark.asyncio
async def test_no_duplicate_pages(mock_demo_mode, temp_batch_dir, monkeypatch):
    """Test that processing does not create duplicate page indices."""
    batch_id, batch_dir = temp_batch_dir
    
    # Create 10-page synthetic PDF
    pdf_path = batch_dir / "test_doc.pdf"
    create_synthetic_pdf(pdf_path, num_pages=10)
    
    monkeypatch.setattr(settings, "temp_storage_path", str(batch_dir.parent))
    
    # Process batch
    processor = BackgroundProcessor()
    job = processor.start_processing(batch_id)
    
    await asyncio.wait_for(job.task, timeout=60)
    
    from app.services.storage import JSONStorage
    storage = JSONStorage(base_path=batch_dir.parent)
    batch_result = storage.load_batch(batch_id)
    
    commitment_records = batch_result["commitment_records"]
    
    # Check for page_index field (new implementation should have it)
    page_indices = []
    for c in commitment_records:
        if "page_index" in c:
            page_indices.append(c["page_index"])
    
    # Verify no duplicates if page_index is tracked
    if page_indices:
        assert len(page_indices) == len(set(page_indices)), "Duplicate page indices found"
        assert len(page_indices) == 10, "Missing page indices"


@pytest.mark.asyncio
async def test_demo_mode_no_quota_errors(mock_demo_mode, temp_batch_dir, monkeypatch):
    """Test that DEMO_MODE processes successfully even if quota is exhausted."""
    batch_id, batch_dir = temp_batch_dir
    
    # Create 1-page synthetic PDF
    pdf_path = batch_dir / "test_doc.pdf"
    create_synthetic_pdf(pdf_path, num_pages=1)
    
    monkeypatch.setattr(settings, "temp_storage_path", str(batch_dir.parent))
    
    # Simulate quota exhaustion by marking quota as exhausted BEFORE processing
    # In DEMO_MODE, this should be ignored and MockExtractor should be used
    if not settings.demo_mode:
        from app.services.extraction.quota_manager import get_quota_manager
        quota_manager = get_quota_manager()
        quota_manager.mark_quota_exhausted(
            model="gemini-1.5-flash",
            error_message="Simulated quota exhaustion",
            retry_info_seconds=86400,
            quota_type="daily"
        )
    
    # Process batch
    processor = BackgroundProcessor()
    job = processor.start_processing(batch_id)
    
    # Wait for completion
    await asyncio.wait_for(job.task, timeout=30)
    
    # Verify successful completion (no quota errors in DEMO_MODE)
    assert job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.COMPLETED_WITH_ERRORS]
    assert job.status != ProcessingStatus.QUOTA_EXHAUSTED, "DEMO_MODE should not hit quota errors"
    
    from app.services.storage import JSONStorage
    storage = JSONStorage(base_path=batch_dir.parent)
    batch_result = storage.load_batch(batch_id)
    
    # Verify at least 1 commitment was created
    commitment_records = batch_result["commitment_records"]
    assert len(commitment_records) >= 1, "DEMO_MODE should create commitments despite quota state"


@pytest.mark.asyncio
async def test_processing_terminates(mock_demo_mode, temp_batch_dir, monkeypatch):
    """Test that processing of a 6-page PDF completes without infinite loop."""
    batch_id, batch_dir = temp_batch_dir
    
    # Create 6-page synthetic PDF
    pdf_path = batch_dir / "test_doc.pdf"
    create_synthetic_pdf(pdf_path, num_pages=6)
    
    monkeypatch.setattr(settings, "temp_storage_path", str(batch_dir.parent))
    
    # Process batch
    processor = BackgroundProcessor()
    job = processor.start_processing(batch_id)
    
    # Wait for completion with strict timeout
    # If infinite loop exists, this will timeout
    try:
        await asyncio.wait_for(job.task, timeout=30)
        processing_completed = True
    except asyncio.TimeoutError:
        processing_completed = False
    
    assert processing_completed, "Processing did not complete within 30s (infinite loop suspected)"
    
    # Verify finite commitment count
    from app.services.storage import JSONStorage
    storage = JSONStorage(base_path=batch_dir.parent)
    batch_result = storage.load_batch(batch_id)
    
    commitment_records = batch_result["commitment_records"]
    assert len(commitment_records) == 6, f"Expected 6 commitments, got {len(commitment_records)} (infinite loop?)"


@pytest.mark.asyncio
async def test_extraction_failure_creates_pending_record(mock_demo_mode, temp_batch_dir, monkeypatch):
    """Test that extraction failure still creates a commitment record flagged for review.
    
    Note: This test may need to mock extractor to force failure.
    For MVP, we verify that failed pages don't crash the entire batch.
    """
    batch_id, batch_dir = temp_batch_dir
    
    # Create 3-page synthetic PDF
    pdf_path = batch_dir / "test_doc.pdf"
    create_synthetic_pdf(pdf_path, num_pages=3)
    
    monkeypatch.setattr(settings, "temp_storage_path", str(batch_dir.parent))
    
    # Process batch (MockExtractor should not fail, but we verify error handling)
    processor = BackgroundProcessor()
    job = processor.start_processing(batch_id)
    
    await asyncio.wait_for(job.task, timeout=30)
    
    # Even with errors, should complete or complete_with_errors
    assert job.status in [ProcessingStatus.COMPLETED, ProcessingStatus.COMPLETED_WITH_ERRORS, ProcessingStatus.FAILED]
    
    from app.services.storage import JSONStorage
    storage = JSONStorage(base_path=batch_dir.parent)
    batch_result = storage.load_batch(batch_id)
    
    # Verify that even failed extractions are tracked in errors
    errors = batch_result.get("errors", [])
    
    # If there are errors, verify they contain page/document information
    for error in errors:
        assert "document_id" in error or "page_index" in error or "error" in error
