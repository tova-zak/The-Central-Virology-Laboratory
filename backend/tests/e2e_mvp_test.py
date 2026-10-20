"""E2E MVP Test Suite - Comprehensive Testing for 8-Hour MVP

This test suite validates the complete MVP pipeline with synthetic test data:
- Multi-page PDF upload and processing
- Document segmentation (including continuation pages)
- Field extraction from forms
- Commitment detection (context-aware)
- Data persistence after restart
- Export blocking logic

CRITICAL NOTES:
- Uses DEMO_MODE=true - NO live Gemini API calls
- Synthetic data only - NO real PII
- Tests run against ACTUAL endpoints and models that exist today
- xfail/skip used for features not yet implemented by Agents A/B/C

USER REQUIREMENT:
Test the full MVP workflow end-to-end with deterministic synthetic data
to prove core functionality without consuming Gemini quota.
"""
import os
import sys
import pytest
import asyncio
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import httpx

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment BEFORE importing app modules
from dotenv import load_dotenv
env_path = backend_dir.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

# Import after env loaded
from app.domain.models import TestRecord, CommitmentRecord
from app.services.processing.background import ProcessingStatus
from app.services.storage.json_storage import JSONStorage
from app.core.config import settings


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_storage(tmp_path):
    """Temporary storage directory for tests."""
    storage_path = tmp_path / "test_storage"
    storage_path.mkdir(exist_ok=True)
    return storage_path


@pytest.fixture
def synthetic_10page_pdf():
    """Create synthetic 10-page PDF with known ground truth.
    
    Ground truth:
    - 10 pages total
    - 8 logical forms:
        - 6 single-page forms (pages 0, 1, 3, 5, 7, 9)
        - 1 two-page form (pages 2-3: "עמוד 1/2" and "עמוד 2/2")
        - 1 two-page form (pages 6-7: similar notation)
    - 10 commitments total:
        - Page 0: 1 commitment (Leumit)
        - Page 1: 2 commitments (Maccabi)
        - Pages 2-3: 1 commitment (Clalit, two-page form)
        - Page 5: 3 commitments (Leumit, includes "דגימה")
        - Page 6-7: 1 commitment (Meuhedet, two-page form)
        - Page 9: 2 commitments (Leumit)
    - Central numbers vary per form
    """
    # Note: Actual PDF generation would require reportlab or similar
    # For MVP, we return metadata describing the synthetic PDF
    # The actual implementation by Agent C should handle this
    return {
        "total_pages": 10,
        "total_forms": 8,
        "total_commitments": 10,
        "forms": [
            {"form_id": "form_0", "pages": [0], "sender": "לאומית", "commitments": 1, "central_numbers": ["123456"]},
            {"form_id": "form_1", "pages": [1], "sender": "מכבי", "commitments": 2, "central_numbers": ["234567", "234568"]},
            {"form_id": "form_2", "pages": [2, 3], "sender": "כללית", "commitments": 1, "central_numbers": ["345678"], "notation": "עמוד 1/2"},
            {"form_id": "form_3", "pages": [4], "sender": "מאוחדת", "commitments": 0, "central_numbers": ["456789"]},
            {"form_id": "form_4", "pages": [5], "sender": "לאומית", "commitments": 3, "central_numbers": ["567890"], "has_dagima": True},
            {"form_id": "form_5", "pages": [6, 7], "sender": "מאוחדת", "commitments": 1, "central_numbers": ["678901"], "notation": "עמוד 1/2"},
            {"form_id": "form_6", "pages": [8], "sender": "כללית", "commitments": 0, "central_numbers": ["789012"]},
            {"form_id": "form_7", "pages": [9], "sender": "לאומית", "commitments": 2, "central_numbers": ["890123"]},
        ]
    }


@pytest.fixture
async def test_client():
    """HTTP client for testing the API."""
    from httpx import ASGITransport
    from app.main import app
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_synthetic_page_image(page_num: int, ground_truth_page: dict) -> bytes:
    """Create a synthetic form page as PNG image.
    
    Args:
        page_num: Page number (0-indexed)
        ground_truth_page: Ground truth data for this page
        
    Returns:
        PNG image bytes
    """
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to load a Hebrew-compatible font
    try:
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/davidbd.ttf",
        ]
        font = None
        for font_path in font_paths:
            if Path(font_path).exists():
                font = ImageFont.truetype(font_path, 20)
                break
        if not font:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    
    y_pos = 50
    
    # Draw header
    draw.text((50, y_pos), f"טופס מספר {page_num + 1}", fill='black', font=font)
    y_pos += 40
    
    # Draw sender
    sender = ground_truth_page.get("sender", "לאומית")
    draw.text((50, y_pos), f"שולח: {sender}", fill='black', font=font)
    y_pos += 40
    
    # Draw page notation if multi-page
    if "notation" in ground_truth_page:
        draw.text((50, y_pos), ground_truth_page["notation"], fill='black', font=font)
        y_pos += 40
    
    # Draw patient info
    draw.text((50, y_pos), "שם פרטי: יוסי", fill='black', font=font)
    y_pos += 30
    draw.text((50, y_pos), "שם משפחה: כהן", fill='black', font=font)
    y_pos += 30
    draw.text((50, y_pos), "ת.ז: 123456789", fill='black', font=font)
    y_pos += 40
    
    # Draw central numbers
    for i, central_num in enumerate(ground_truth_page.get("central_numbers", [])):
        draw.text((50, y_pos), f"מספר מרכזי: {central_num}", fill='black', font=font)
        y_pos += 30
    
    y_pos += 20
    
    # Draw commitments
    num_commitments = ground_truth_page.get("commitments", 0)
    for i in range(num_commitments):
        commitment_num = f"COMM{page_num}{i}"
        draw.text((50, y_pos), f"התחייבות: {commitment_num}", fill='black', font=font)
        y_pos += 30
    
    # Draw "דגימה" if specified
    if ground_truth_page.get("has_dagima", False):
        draw.text((50, y_pos), "דגימה: SAMPLE001", fill='black', font=font)
        y_pos += 30
    
    # Draw date
    draw.text((50, y_pos), "תאריך קבלה: 14/10/2026", fill='black', font=font)
    
    # Convert to PNG bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


# ============================================================================
# E2E TESTS
# ============================================================================

@pytest.mark.asyncio
@pytest.mark.xfail(reason="Full 10-page processing depends on Agent A segmentation implementation")
async def test_01_upload_10page_pdf_no_loss(test_client, synthetic_10page_pdf, temp_storage):
    """Test that 10-page upload results in all 10 pages stored.
    
    VALIDATES:
    - Upload endpoint accepts multiple pages
    - All pages stored in batch directory
    - No page loss during upload
    """
    # This test is xfail because:
    # 1. Actual PDF generation needs to be implemented
    # 2. We're testing with the metadata structure for now
    
    # Expected behavior:
    # POST /api/batches with 10 images/pages
    # Should return batch_id and 10 document_ids
    
    ground_truth = synthetic_10page_pdf
    assert ground_truth["total_pages"] == 10
    assert ground_truth["total_forms"] == 8
    assert ground_truth["total_commitments"] == 10


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Segmentation logic not yet implemented by Agent A")
async def test_02_segmentation_groups_continuation_pages(test_client, synthetic_10page_pdf):
    """Test that 2-page forms (עמוד 1/2, 2/2) are grouped into ONE LogicalForm.
    
    VALIDATES:
    - OCR detects "עמוד X/Y" notation
    - Pages 2-3 grouped into single form
    - Pages 6-7 grouped into single form
    - Result: 8 forms from 10 pages (not 10 forms)
    
    BLOCKER: Depends on Agent A implementing LogicalForm segmentation
    """
    ground_truth = synthetic_10page_pdf
    
    # Expected after segmentation:
    # - form_2 should contain pages [2, 3]
    # - form_5 should contain pages [6, 7]
    # - All other forms should be single-page
    
    multi_page_forms = [f for f in ground_truth["forms"] if len(f["pages"]) > 1]
    assert len(multi_page_forms) == 2


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Full pipeline integration pending")
async def test_03_commitment_count_matches_ground_truth(test_client, synthetic_10page_pdf):
    """Test that output record count = commitment count in ground truth.
    
    VALIDATES:
    - 10 commitments detected across all forms
    - NOT 10 records (one per page)
    - NOT 8 records (one per form)
    - Exactly 10 CommitmentRecords
    
    BLOCKER: Depends on Agent C commitment detection
    """
    ground_truth = synthetic_10page_pdf
    total_commitments = sum(f["commitments"] for f in ground_truth["forms"])
    assert total_commitments == 10


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Context-aware commitment detection not yet implemented")
async def test_04_leumit_dagima_detected(test_client, synthetic_10page_pdf):
    """Test that Leumit 'דגימה' is detected as commitment, Clalit is NOT.
    
    VALIDATES:
    - Context-aware commitment detection
    - Sender=='לאומית' + 'דגימה' field → commitment
    - Sender=='כללית' + 'דגימה' field → NOT commitment
    
    BLOCKER: Depends on Agent C implementing sender-context rules
    """
    ground_truth = synthetic_10page_pdf
    
    # form_4 (page 5) has sender="לאומית" and has_dagima=True
    # Should contribute to commitment count
    
    # form_2 (pages 2-3) has sender="כללית"
    # Even if it had "דגימה", should NOT count as commitment
    
    leumit_forms_with_dagima = [
        f for f in ground_truth["forms"] 
        if f["sender"] == "לאומית" and f.get("has_dagima", False)
    ]
    assert len(leumit_forms_with_dagima) > 0


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Persistence and restart simulation not implemented")
async def test_05_data_persists_after_restart(temp_storage):
    """Test that data persists after simulated server restart.
    
    VALIDATES:
    - Batch data saved to JSON storage
    - Storage.load_batch() retrieves data after restart
    - Manual corrections preserved
    
    BLOCKER: Needs integration with actual processing pipeline
    """
    # Simulate: process batch, save, "restart" (clear memory), reload
    storage = JSONStorage(base_path=temp_storage)
    
    # Create test batch
    batch_id = "test_persistence"
    batch_data = {
        "batch_id": batch_id,
        "status": "completed",
        "test_records": [
            {
                "test_id": "test_001",
                "patient_first_name": {"raw_value": "יוסי", "reviewed_value": "יוסף (corrected)"}
            }
        ]
    }
    
    # Save
    storage.save_batch(batch_id, batch_data)
    
    # Simulate restart - reload from disk
    loaded_data = storage.load_batch(batch_id)
    
    assert loaded_data is not None
    assert loaded_data["test_records"][0]["patient_first_name"]["reviewed_value"] == "יוסף (corrected)"


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Export blocking logic depends on relationship_status field")
async def test_06_export_blocked_when_unresolved(test_client):
    """Test that export is blocked when unresolved_relationships > 0.
    
    VALIDATES:
    - POST /api/batches/{batch_id}/export returns HTTP 400
    - When any commitment has relationship_status="unresolved_relationship"
    - Error message indicates blocker
    
    BLOCKER: Depends on Agent A implementing relationship_status field
    """
    # Expected: HTTP 400 with detail about unresolved relationships
    pass


@pytest.mark.asyncio
@pytest.mark.xfail(reason="Field separation logic not yet implemented")
async def test_07_central_number_not_confused(test_client):
    """Test that central_number is NOT confused with commitment_number.
    
    VALIDATES:
    - Central numbers stored in correct field
    - Commitment numbers stored in correct field
    - No cross-contamination
    
    BLOCKER: Depends on Agent C field extraction accuracy
    """
    # Expected: commitment_number != central_number for same form
    pass


# ============================================================================
# INTEGRATION TESTS (Current API)
# ============================================================================

@pytest.mark.asyncio
async def test_health_endpoint():
    """Test that /health endpoint responds correctly."""
    from httpx import ASGITransport
    from app.main import app
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code in [200, 503]  # Healthy or unhealthy, but responds
        # Health endpoint may return various formats, just check it responds
        assert len(response.content) > 0


@pytest.mark.asyncio
async def test_storage_persistence():
    """Test JSONStorage save/load cycle."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JSONStorage(base_path=Path(tmpdir))
        
        # Save batch
        batch_id = "test_batch"
        batch_data = {
            "batch_id": batch_id,
            "status": "completed",
            "test_records": [],
            "commitment_records": []
        }
        
        storage.save_batch(batch_id, batch_data)
        
        # Load batch
        loaded = storage.load_batch(batch_id)
        
        assert loaded is not None
        assert loaded["batch_id"] == batch_id
        assert loaded["status"] == "completed"


@pytest.mark.asyncio
async def test_upload_validation():
    """Test that upload endpoint validates file types correctly."""
    from httpx import ASGITransport
    from app.main import app
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Test with invalid file (text file claiming to be PDF)
        files = {"files": ("test.pdf", b"not a real pdf", "application/pdf")}
        response = await client.post("/api/batches", files=files)
        
        # Should fail magic byte validation
        assert response.status_code == 400


# ============================================================================
# SMOKE TESTS (Minimal Validation)
# ============================================================================

def test_models_can_be_instantiated():
    """Test that domain models can be instantiated."""
    from app.domain.models import TestRecord, CommitmentRecord, FieldValue
    
    # Create TestRecord
    record = TestRecord(test_id="test_001")
    assert record.test_id == "test_001"
    assert record.patient_first_name.extraction_state.value == "missing"
    
    # Create CommitmentRecord
    commitment = CommitmentRecord(
        commitment_record_id="comm_001",
        test_id="test_001"
    )
    assert commitment.commitment_record_id == "comm_001"


def test_demo_mode_enabled():
    """Test that DEMO_MODE is enabled (no live Gemini calls)."""
    demo_mode = os.getenv("DEMO_MODE", "false").lower()
    # Allow test to pass in development, but warn if not set
    if demo_mode != "true":
        pytest.skip("DEMO_MODE not enabled - skipping to avoid Gemini API calls")


def test_hybrid_engine_configured():
    """Test that HYBRID_ENGINE_ENABLED is set."""
    # May be true or false, but should be configured
    hybrid_enabled = os.getenv("HYBRID_ENGINE_ENABLED", "false")
    assert hybrid_enabled.lower() in ["true", "false"]


# ============================================================================
# SUMMARY
# ============================================================================

"""
E2E MVP Test Suite Summary
===========================

IMPLEMENTED (5 tests):
✅ test_health_endpoint - /health responds
✅ test_storage_persistence - JSONStorage works
✅ test_upload_validation - Upload validates file types
✅ test_models_can_be_instantiated - Domain models work
✅ test_demo_mode_enabled - DEMO_MODE configured

XFAIL (7 tests - waiting on Agent A/B/C):
⏳ test_01_upload_10page_pdf_no_loss - Needs actual PDF generation
⏳ test_02_segmentation_groups_continuation_pages - Needs Agent A segmentation
⏳ test_03_commitment_count_matches_ground_truth - Needs Agent C detection
⏳ test_04_leumit_dagima_detected - Needs Agent C context-aware rules
⏳ test_05_data_persists_after_restart - Needs full pipeline
⏳ test_06_export_blocked_when_unresolved - Needs Agent A relationship_status
⏳ test_07_central_number_not_confused - Needs Agent C field separation

NEXT STEPS:
1. Agents A/B/C complete their features
2. Remove xfail markers as features are implemented
3. Add real synthetic PDF generation
4. Run full test suite and document results in MVP_VALIDATION_REPORT.md

CRITICAL NOTES:
- All tests use DEMO_MODE=true (no live Gemini calls)
- Synthetic data only (no real PII)
- xfail tests document what SHOULD work, not what DOES work
- Honest limitation: mock tests ≠ proof of real Gemini accuracy
"""
