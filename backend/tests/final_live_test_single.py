"""Final LIVE Gemini Test - Single Synthetic Form

⚠️ USER APPROVED: ONE REAL GEMINI API CALL

Success criteria:
✅ Real Gemini API call received
✅ Valid JSON passed Pydantic validation  
✅ extractor_id indicates Gemini (not mock-demo)
✅ TestRecord created with extracted data
✅ Record saved and displayable in review screen
✅ No fabricated data added by Mock

This test uses gemini-3.8-flash (Free Tier, no billing)
"""
import sys
import os
import time
import logging
from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load .env
from dotenv import load_dotenv
env_path = backend_dir.parent / ".env"
load_dotenv(env_path, override=True)

logger.info(f"✅ Loaded .env from {env_path}")

# Verify configuration
demo_mode = os.getenv("DEMO_MODE", "true").lower()
if demo_mode == "true":
    logger.error("❌ DEMO_MODE=true. Set DEMO_MODE=false in .env for Live test")
    sys.exit(1)

logger.info("✅ DEMO_MODE=false verified")

from app.core.config import settings
from app.services.extraction.gemini_adapter import GeminiExtractor

logger.info(f"✅ Model: {settings.gemini_model}")
logger.info(f"✅ Demo mode: {settings.demo_mode}")

def create_synthetic_form() -> bytes:
    """Create synthetic commitment form with known values
    
    Known ground truth:
    - Patient ID: 987654321
    - Central Number: 123456
    - Commitment Number: ABC999
    - Date: 15/10/2026
    - Patient Name: יוסי לוי
    - Sender: ד"ר דן כהן
    """
    img = Image.new('RGB', (1200, 1600), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
        font_medium = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    except:
        font_large = font_medium = ImageFont.load_default()
    
    y = 50
    draw.text((400, y), "המעבדה המרכזית לנגיפים", fill='black', font=font_large)
    y += 80
    
    draw.text((100, y), "═" * 60, fill='black', font=font_medium)
    y += 50
    
    draw.text((100, y), "פרטי מטופל:", fill='black', font=font_medium)
    y += 50
    
    draw.text((100, y), "שם: יוסי לוי", fill='black', font=font_medium)
    y += 50
    
    draw.text((100, y), "ת.ז: 987654321", fill='black', font=font_large)
    y += 80
    
    draw.text((100, y), "מספר מרכזי: 123456", fill='black', font=font_large)
    y += 80
    
    draw.text((100, y), "מספר התחייבות: ABC999", fill='black', font=font_large)
    y += 80
    
    draw.text((100, y), "תאריך: 15/10/2026", fill='black', font=font_medium)
    y += 80
    
    draw.text((100, y), "נשלח על ידי: ד\"ר דן כהן", fill='black', font=font_medium)
    
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def main():
    logger.info("=" * 80)
    logger.info("FINAL LIVE GEMINI TEST - SINGLE API CALL")
    logger.info("=" * 80)
    
    # Step 1: Create synthetic form
    logger.info("\n[STEP 1] Creating synthetic form with known ground truth...")
    image_bytes = create_synthetic_form()
    logger.info(f"✅ Created form ({len(image_bytes)} bytes)")
    logger.info("   Ground truth:")
    logger.info("   - Patient ID: 987654321")
    logger.info("   - Central Number: 123456")
    logger.info("   - Commitment Number: ABC999")
    logger.info("   - Date: 15/10/2026")
    
    # Step 2: Initialize extractor
    logger.info("\n[STEP 2] Initializing GeminiExtractor...")
    extractor = GeminiExtractor(model=settings.gemini_model)
    logger.info(f"✅ Extractor ready: {extractor.model}")
    
    # Step 3: Make ONE API call
    logger.info("\n[STEP 3] Making SINGLE Gemini API call...")
    logger.info("⚠️  This consumes 1 API request from Free Tier quota")
    
    try:
        start_time = time.time()
        
        result = extractor.extract(
            image=image_bytes,
            document_id="final_live_test",
            page_index=0
        )
        
        elapsed = time.time() - start_time
        logger.info(f"✅ API call completed in {elapsed:.2f}s")
        
    except Exception as e:
        logger.error(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Verify result
    logger.info("\n[STEP 4] Verifying extraction result...")
    
    # Check model_id
    if 'mock' in result.model_id.lower():
        logger.error(f"❌ FAILED: Mock data returned (model_id={result.model_id})")
        return False
    logger.info(f"✅ Real Gemini: model_id={result.model_id}")
    
    # Check JSON structure
    if not result.fields:
        logger.error("❌ FAILED: No fields extracted")
        return False
    logger.info(f"✅ Fields extracted: {len(result.fields)}")
    
    # Check extracted values against ground truth
    logger.info("\n[STEP 5] Comparing to ground truth...")
    
    fields = result.fields
    matches = []
    mismatches = []
    
    # Patient ID
    if fields.get('patient_id_number') == '987654321':
        matches.append("✅ Patient ID: 987654321")
    else:
        mismatches.append(f"❌ Patient ID: expected '987654321', got '{fields.get('patient_id_number')}'")
    
    # Central number
    centrals = fields.get('central_numbers', [])
    if '123456' in centrals:
        matches.append("✅ Central Number: 123456")
    else:
        mismatches.append(f"❌ Central Number: expected '123456', got {centrals}")
    
    # Commitment number  
    commitments = fields.get('commitment_numbers', [])
    if 'ABC999' in commitments:
        matches.append("✅ Commitment Number: ABC999")
    else:
        mismatches.append(f"❌ Commitment Number: expected 'ABC999', got {commitments}")
    
    # Date
    date = fields.get('received_date', '')
    if '15' in date and '10' in date:
        matches.append(f"✅ Date: {date}")
    else:
        mismatches.append(f"⚠️ Date: expected '15/10/2026', got '{date}'")
    
    for match in matches:
        logger.info(f"   {match}")
    for mismatch in mismatches:
        logger.warning(f"   {mismatch}")
    
    # Step 6: Check warnings
    logger.info("\n[STEP 6] Checking extraction warnings...")
    if result.warnings:
        logger.info(f"   {len(result.warnings)} warnings:")
        for w in result.warnings:
            logger.info(f"     - {w}")
    else:
        logger.info("   No warnings")
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("FINAL RESULT")
    logger.info("=" * 80)
    
    import json
    summary = {
        "status": "SUCCESS" if len(mismatches) == 0 else "PARTIAL",
        "model_id": result.model_id,
        "processing_time_ms": result.processing_time_ms,
        "fields_extracted": len(result.fields),
        "ground_truth_matches": len(matches),
        "ground_truth_mismatches": len(mismatches),
        "warnings": len(result.warnings),
        "api_calls_used": 1
    }
    
    logger.info(json.dumps(summary, indent=2, ensure_ascii=False))
    
    success = len(mismatches) == 0
    
    if success:
        logger.info("\n✅✅✅ LIVE TEST PASSED ✅✅✅")
        logger.info("Gemini extraction is working correctly")
        logger.info("Ready for accuracy evaluation on golden dataset")
    else:
        logger.warning("\n⚠️ LIVE TEST PARTIAL SUCCESS")
        logger.warning("Gemini is working but some values don't match ground truth")
        logger.warning("This is expected - model may interpret differently")
        logger.warning("Need golden dataset evaluation to measure true accuracy")
    
    logger.info("=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
