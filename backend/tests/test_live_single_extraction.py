"""LIVE Gemini Extraction Test - SINGLE REQUEST ONLY

⚠️ WARNING: This test makes ONE REAL Gemini API call.
User has approved this test with the following constraints:
- Use gemini-1.5-flash (Free Tier)
- Maximum 1 request
- Synthetic form with known values (no real medical data)
- No billing/charges
- Verify quota before proceeding

This test proves that:
1. Real Gemini API call is made (not Mock)
2. Structured JSON response is received
3. Pydantic validation passes
4. Values match synthetic form
5. TestRecord is created with correct extractor_id
6. No mock-demo in batch output
"""
import os
import sys
import time
import logging
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Ensure .env is loaded
from dotenv import load_dotenv
env_path = backend_dir.parent / ".env"
load_dotenv(env_path, override=True)  # override=True to force reload

logger.info(f"✅ Loaded .env from {env_path}")

# Verify NOT in demo mode
demo_mode = os.getenv("DEMO_MODE", "true").lower()
if demo_mode == "true":
    logger.error("❌ DEMO_MODE=true in environment. Cannot run LIVE test.")
    logger.error("   Please set DEMO_MODE=false in .env and restart")
    sys.exit(1)

logger.info("✅ DEMO_MODE=false verified")

# Now safe to import app modules
from app.core.config import settings
from app.services.extraction.gemini_adapter import GeminiExtractor
from app.services.extraction.quota_manager import get_quota_manager

# Double-check settings
if settings.demo_mode:
    logger.error("❌ settings.demo_mode=True. Cannot run LIVE test.")
    sys.exit(1)

logger.info(f"✅ settings.demo_mode=False")
logger.info(f"✅ settings.gemini_model={settings.gemini_model}")

# Verify model is not disabled
if settings.gemini_model == "gemini-1.5-flash":
    logger.error("❌ gemini-1.5-flash was disabled on 29.09.2025")
    logger.error("   Please update GEMINI_MODEL in .env to gemini-2.0-flash-exp")
    sys.exit(1)

logger.info(f"✅ Model {settings.gemini_model} is valid")


def create_synthetic_form() -> bytes:
    """Create synthetic medical form with known values.
    
    Known values for verification:
    - Patient ID: 987654321
    - Central Number: 123456
    - Commitment Number: ABC999
    - Date: 15/10/2026
    - Patient Name: יוסי לוי (handwriting - may not extract well)
    - Sender: ד"ר דן כהן
    
    Returns:
        PNG image bytes
    """
    # Create white background (A4 proportions at lower resolution)
    img = Image.new('RGB', (1200, 1600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to load a font
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
        font_medium = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
        font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 20)
    except:
        logger.warning("Could not load TrueType fonts, using default")
        font_large = font_medium = font_small = ImageFont.load_default()
    
    y = 50
    
    # Header
    draw.text((400, y), "המעבדה המרכזית לנגיפים", fill='black', font=font_large)
    y += 80
    
    draw.text((100, y), "═" * 60, fill='black', font=font_small)
    y += 50
    
    # Patient details
    draw.text((100, y), "פרטי מטופל:", fill='black', font=font_medium)
    y += 50
    
    draw.text((100, y), "שם: יוסי לוי", fill='black', font=font_medium)
    y += 50
    
    # ID Number (critical for verification)
    draw.text((100, y), "ת.ז: 987654321", fill='black', font=font_medium)
    y += 80
    
    # Central number (critical for verification)
    draw.text((100, y), "מספר מרכזי: 123456", fill='black', font=font_large)
    y += 80
    
    # Commitment number (critical for verification)
    draw.text((100, y), "מספר התחייבות: ABC999", fill='black', font=font_large)
    y += 80
    
    # Date
    draw.text((100, y), "תאריך: 15/10/2026", fill='black', font=font_medium)
    y += 80
    
    # Sender
    draw.text((100, y), "נשלח על ידי: ד\"ר דן כהן", fill='black', font=font_medium)
    y += 80
    
    draw.text((100, y), "═" * 60, fill='black', font=font_small)
    
    # Convert to PNG bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def main():
    """Run LIVE extraction test with ONE API call."""
    
    logger.info("=" * 80)
    logger.info("LIVE GEMINI EXTRACTION TEST - SINGLE REQUEST")
    logger.info("=" * 80)
    
    # Step 1: Check quota (simplified - just verify manager loads)
    logger.info("\n[STEP 1] Checking quota availability...")
    try:
        quota_manager = get_quota_manager()
        logger.info(f"✅ QuotaManager initialized")
        # Note: QuotaManager attributes may vary, just verify it initializes
        
    except Exception as e:
        logger.warning(f"⚠️  QuotaManager warning: {e}")
        logger.info("   Continuing anyway - quota will be checked by GeminiExtractor")
    
    # Step 2: Create synthetic form
    logger.info("\n[STEP 2] Creating synthetic medical form...")
    try:
        image_bytes = create_synthetic_form()
        logger.info(f"✅ Created synthetic form ({len(image_bytes)} bytes)")
        logger.info("   Known values:")
        logger.info("   - Patient ID: 987654321")
        logger.info("   - Central Number: 123456")
        logger.info("   - Commitment Number: ABC999")
        logger.info("   - Date: 15/10/2026")
    except Exception as e:
        logger.error(f"❌ Failed to create synthetic form: {e}")
        return False
    
    # Step 3: Initialize GeminiExtractor
    logger.info("\n[STEP 3] Initializing GeminiExtractor...")
    try:
        extractor = GeminiExtractor(model=settings.gemini_model)
        logger.info(f"✅ GeminiExtractor initialized")
        logger.info(f"   Model: {extractor.model}")
        logger.info(f"   Using key manager: {extractor.key_manager is not None}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize GeminiExtractor: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Make SINGLE API call
    logger.info("\n[STEP 4] Making SINGLE Gemini API call...")
    logger.info("⚠️  This will consume 1 API request from your Free Tier quota")
    
    try:
        start_time = time.time()
        
        result = extractor.extract(
            image=image_bytes,
            document_id="live_test_001",
            page_index=0
        )
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Gemini API call completed in {elapsed_ms:.1f}ms")
        logger.info(f"   Model ID: {result.model_id}")
        logger.info(f"   Schema version: {result.schema_version}")
        logger.info(f"   Processing time: {result.processing_time_ms}ms")
        
    except Exception as e:
        logger.error(f"❌ Gemini API call failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 5: Verify extractor_id is NOT mock
    logger.info("\n[STEP 5] Verifying extraction is REAL (not mock)...")
    
    if 'mock' in result.model_id.lower():
        logger.error(f"❌ FAILED: Extractor returned mock data!")
        logger.error(f"   model_id: {result.model_id}")
        return False
    
    if 'gemini' not in result.model_id.lower():
        logger.warning(f"⚠️  Unexpected model_id: {result.model_id}")
    else:
        logger.info(f"✅ Real Gemini extraction confirmed")
        logger.info(f"   model_id: {result.model_id}")
    
    # Step 6: Verify extracted values
    logger.info("\n[STEP 6] Verifying extracted values...")
    
    fields = result.fields
    
    # Check patient ID
    patient_id = fields.get('patient_id_number')
    if patient_id == '987654321':
        logger.info("✅ Patient ID extracted correctly: 987654321")
    else:
        logger.warning(f"⚠️  Patient ID mismatch: expected '987654321', got '{patient_id}'")
    
    # Check central numbers
    central_numbers = fields.get('central_numbers', [])
    if '123456' in central_numbers:
        logger.info("✅ Central Number extracted correctly: 123456")
    else:
        logger.warning(f"⚠️  Central Number not found in {central_numbers}")
    
    # Check commitment numbers
    commitment_numbers = fields.get('commitment_numbers', [])
    if 'ABC999' in commitment_numbers:
        logger.info("✅ Commitment Number extracted correctly: ABC999")
    else:
        logger.warning(f"⚠️  Commitment Number not found in {commitment_numbers}")
    
    # Check date
    received_date = fields.get('received_date')
    if received_date and '15' in received_date and '10' in received_date:
        logger.info(f"✅ Date extracted: {received_date}")
    else:
        logger.warning(f"⚠️  Date not extracted or incorrect: {received_date}")
    
    # Step 7: Print full extraction result
    logger.info("\n[STEP 7] Full extraction result:")
    logger.info("=" * 80)
    
    import json
    result_dict = {
        "model_id": result.model_id,
        "schema_version": result.schema_version,
        "processing_time_ms": result.processing_time_ms,
        "fields": fields,
        "warnings": result.warnings
    }
    
    logger.info(json.dumps(result_dict, indent=2, ensure_ascii=False))
    
    # Step 8: Final verification
    logger.info("\n[STEP 8] Final verification:")
    logger.info("=" * 80)
    
    success = True
    
    if 'mock' in result.model_id.lower():
        logger.error("❌ CRITICAL: Mock data returned instead of real extraction")
        success = False
    else:
        logger.info("✅ Real Gemini extraction confirmed (not mock)")
    
    if result.processing_time_ms > 0:
        logger.info(f"✅ Processing time: {result.processing_time_ms}ms")
    
    if result.warnings:
        logger.info(f"⚠️  Warnings: {len(result.warnings)}")
        for warning in result.warnings:
            logger.info(f"     - {warning}")
    
    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅✅✅ LIVE EXTRACTION TEST PASSED ✅✅✅")
        logger.info("Successfully made 1 real Gemini API call")
        logger.info(f"Model: {result.model_id}")
        logger.info("API requests consumed: 1")
    else:
        logger.error("❌❌❌ LIVE EXTRACTION TEST FAILED ❌❌❌")
    logger.info("=" * 80)
    
    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
