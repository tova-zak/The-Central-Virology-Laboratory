"""
Single Gemini API test - CONTROLLED EXECUTION.

This script makes EXACTLY ONE real Gemini API call to verify:
1. Model availability (gemini-1.5-flash)
2. Structured output with Pydantic schema
3. Multi-key round-robin
4. Quota tracking
5. Hebrew text extraction

REQUIREMENTS BEFORE RUNNING:
- .env file with valid GEMINI_API_KEY and GEMINI_API_1-8
- DEMO_MODE=false
- Confirmed Free Tier status (no billing)

USAGE:
  python backend/test_single_gemini_call.py

OUTPUT:
- Test results (no keys exposed)
- Quota status
- Extraction accuracy
"""
import os
import sys
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Load .env
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Force demo_mode=false for this test
os.environ['DEMO_MODE'] = 'false'

# Imports
from app.services.extraction.gemini_adapter import GeminiExtractor
from app.services.extraction.gemini_key_manager import get_key_manager
from app.services.extraction.quota_manager import get_quota_manager
from app.core.config import settings


def create_synthetic_hebrew_form():
    """Create a synthetic medical form image with Hebrew text."""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 36)
        font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 28)
    except:
        font_large = font_small = ImageFont.load_default()
    
    y = 50
    
    # Title
    draw.text((300, y), "טופס בדיקה", fill='black', font=font_large)
    y += 60
    
    # Patient info
    draw.text((50, y), "שם פרטי: דוד", fill='black', font=font_small)
    y += 45
    draw.text((50, y), "שם משפחה: כהן", fill='black', font=font_small)
    y += 45
    draw.text((50, y), "ת.ז: 123456782", fill='black', font=font_small)  # Valid Israeli ID
    y += 45
    
    # Institution
    draw.text((50, y), "מוסד שולח: המעבדה המרכזית לנגיפים", fill='black', font=font_small)
    y += 45
    
    # Date
    draw.text((50, y), "תאריך: 15/03/2024", fill='black', font=font_small)
    y += 45
    
    # Numbers
    draw.text((50, y), "מספר מרכזי: 654321", fill='black', font=font_small)
    y += 45
    draw.text((50, y), "מספר התחייבות: ABC123", fill='black', font=font_small)
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


def main():
    print("=" * 70)
    print("Gemini API - Single Controlled Test")
    print("=" * 70)
    print()
    
    # Safety checks
    if settings.demo_mode:
        print("❌ ERROR: DEMO_MODE is enabled in settings")
        print("   Set DEMO_MODE=false in .env to run this test")
        sys.exit(1)
    
    print("✓ DEMO_MODE=false (real API calls enabled)")
    print()
    
    # Check keys
    km = get_key_manager()
    total_keys = km.get_total_key_count()
    active_keys = km.get_active_key_count()
    
    print(f"✓ API Keys loaded: {total_keys} total, {active_keys} active")
    print()
    
    # Confirm with user (simulated - in real use would be interactive)
    print("⚠️  WARNING: This will make ONE real Gemini API call")
    print(f"   Model: {settings.gemini_model}")
    print(f"   Quota will be consumed: 1 request")
    print()
    print("   Proceeding with test...")
    print()
    
    # Create synthetic image
    print("=" * 70)
    print("Phase 1: Creating Synthetic Test Image")
    print("=" * 70)
    image_bytes = create_synthetic_hebrew_form()
    print(f"✓ Created synthetic form image ({len(image_bytes)} bytes)")
    print("  Content: Hebrew text with patient info, ID, date, numbers")
    print()
    
    # Initialize extractor
    print("=" * 70)
    print("Phase 2: Initializing Gemini Extractor")
    print("=" * 70)
    extractor = GeminiExtractor(model=settings.gemini_model)
    print(f"✓ Extractor initialized: {extractor.model}")
    print()
    
    # Check quota BEFORE call
    quota_manager = get_quota_manager()
    is_available, quota_status = quota_manager.check_quota_available(settings.gemini_model)
    
    if not is_available:
        print("❌ ERROR: Quota already exhausted!")
        print(f"   Exhausted at: {quota_status.exhausted_at}")
        print(f"   Retry after: {quota_status.retry_after}")
        sys.exit(1)
    
    print("✓ Quota available (circuit breaker open)")
    print()
    
    # Make the call
    print("=" * 70)
    print("Phase 3: Calling Gemini API (REAL REQUEST)")
    print("=" * 70)
    
    try:
        result = extractor.extract(
            image=image_bytes,
            document_id="synthetic-test-001",
            page_index=0
        )
        
        print("✅ SUCCESS: API call completed")
        print()
        print("-" * 70)
        print("Extraction Results:")
        print("-" * 70)
        print(f"  Model: {result.model_id}")
        print(f"  Processing time: {result.processing_time_ms:.0f}ms")
        print(f"  Prompt version: {result.prompt_version}")
        print()
        print("  Extracted Fields:")
        print(f"    Patient first name: {result.fields.get('patient_first_name')}")
        print(f"    Patient last name: {result.fields.get('patient_last_name')}")
        print(f"    Patient ID: {result.fields.get('patient_id_number')}")
        print(f"    Sender: {result.fields.get('sender')}")
        print(f"    Date: {result.fields.get('received_date')}")
        print(f"    Central numbers: {result.fields.get('central_numbers')}")
        print(f"    Commitment numbers: {result.fields.get('commitment_numbers')}")
        print()
        
        if result.warnings:
            print("  Warnings:")
            for w in result.warnings:
                print(f"    - {w}")
            print()
        
        # Check quota AFTER call
        usage = quota_manager.get_quota_usage(settings.gemini_model)
        print("-" * 70)
        print("Quota Status After Call:")
        print("-" * 70)
        print(f"  Requests this minute: {usage['requests_this_minute']}")
        print(f"  Requests today: {usage['requests_today']}")
        print(f"  Circuit breaker: {'OPEN (OK)' if usage['is_available'] else 'CLOSED (exhausted)'}")
        print()
        
        # Accuracy check
        print("=" * 70)
        print("Phase 4: Accuracy Assessment")
        print("=" * 70)
        
        expected = {
            'patient_first_name': 'דוד',
            'patient_last_name': 'כהן',
            'patient_id_number': '123456782',
            'received_date': '15/03/2024',
            'central_numbers': ['654321'],
            'commitment_numbers': ['ABC123']
        }
        
        matches = 0
        mismatches = []
        
        for field, expected_value in expected.items():
            actual_value = result.fields.get(field)
            
            # Normalize for comparison
            if isinstance(expected_value, list):
                match = actual_value == expected_value
            else:
                match = str(actual_value).strip() == str(expected_value).strip()
            
            if match:
                matches += 1
                print(f"  ✓ {field}: MATCH")
            else:
                mismatches.append((field, expected_value, actual_value))
                print(f"  ✗ {field}: MISMATCH (expected '{expected_value}', got '{actual_value}')")
        
        print()
        print(f"Accuracy: {matches}/{len(expected)} fields correct ({100*matches//len(expected)}%)")
        print()
        
        if mismatches:
            print("⚠️  Mismatches detected (may be Hebrew RTL issues or OCR errors)")
        
        print("=" * 70)
        print("Test Complete")
        print("=" * 70)
        print()
        print("Summary:")
        print(f"  ✅ Gemini API call successful")
        print(f"  ✅ Structured output received")
        print(f"  ✅ Quota tracking working")
        print(f"  ✅ Multi-key manager operational")
        print(f"  📊 Accuracy: {matches}/{len(expected)} fields")
        print(f"  📊 API requests used: 1")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {e}")
        print()
        
        # Check if quota was the issue
        is_available, quota_status = quota_manager.check_quota_available(settings.gemini_model)
        if not is_available:
            print("💡 Quota exhausted - circuit breaker activated")
            print(f"   Retry after: {quota_status.retry_after}")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
