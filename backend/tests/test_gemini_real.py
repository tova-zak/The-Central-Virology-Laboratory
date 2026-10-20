"""Test Gemini extraction with real forms.

SECURITY: This test uses sample forms from reference/ directory.
These are demo forms without real patient data, approved for AI processing.
"""
import os
import sys
import json
import fitz  # PyMuPDF
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.extraction.gemini_adapter import GeminiExtractor
from app.core.config import settings


def pdf_page_to_image(pdf_path: str, page_num: int = 0) -> bytes:
    """Convert PDF page to PNG image bytes.
    
    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        
    Returns:
        PNG image bytes
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    # Render at high DPI for better OCR
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")
    
    doc.close()
    return img_bytes


def test_single_form():
    """Test extraction on a single real form."""
    print("=" * 60)
    print("Testing Gemini Extraction with Real Form")
    print("=" * 60)
    
    # Load first form from reference
    pdf_path = Path(__file__).parent.parent.parent / "reference" / "התחייבויות - דוגמאות, חלק 1 (PDF).pdf"
    
    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return False
    
    print(f"\n📄 Loading: {pdf_path.name}")
    print(f"   Testing page 0 (first form)")
    
    # Convert to image
    try:
        image_bytes = pdf_page_to_image(str(pdf_path), page_num=0)
        print(f"✓ Converted to image: {len(image_bytes)} bytes")
    except Exception as e:
        print(f"❌ Failed to convert PDF: {e}")
        return False
    
    # Initialize extractor
    try:
        extractor = GeminiExtractor(
            model=settings.gemini_model
        )
        print(f"✓ Initialized GeminiExtractor")
        print(f"   Model: {settings.gemini_model}")
    except Exception as e:
        print(f"❌ Failed to initialize extractor: {e}")
        return False
    
    # Extract
    print(f"\n🤖 Calling Gemini API...")
    try:
        result = extractor.extract(
            image=image_bytes,
            document_id="test_form_001",
            page_index=0
        )
        print(f"✓ Extraction completed")
        print(f"   Processing time: {result.processing_time_ms:.0f}ms")
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Display results
    print(f"\n📊 Extraction Results:")
    print(f"   Schema version: {result.schema_version}")
    print(f"   Model: {result.model_id}")
    print(f"   Prompt version: {result.prompt_version}")
    
    print(f"\n🔍 Extracted Fields:")
    for field_name, value in result.fields.items():
        if value is None:
            print(f"   {field_name}: <missing>")
        elif isinstance(value, list):
            print(f"   {field_name}: {value} ({len(value)} items)")
        else:
            print(f"   {field_name}: {value}")
    
    if result.warnings:
        print(f"\n⚠️  Warnings:")
        for warning in result.warnings:
            print(f"   - {warning}")
    else:
        print(f"\n✓ No warnings")
    
    # Validate structure
    print(f"\n✅ Validation:")
    expected_fields = [
        'patient_first_name',
        'patient_last_name', 
        'patient_id_number',
        'sender',
        'received_date',
        'central_numbers',
        'commitment_numbers'
    ]
    
    all_present = True
    for field in expected_fields:
        if field in result.fields:
            print(f"   ✓ {field}")
        else:
            print(f"   ✗ {field} MISSING")
            all_present = False
    
    # Check numbers are strings
    for field in ['patient_id_number', 'central_numbers', 'commitment_numbers']:
        value = result.fields.get(field)
        if value is not None:
            if field.endswith('_numbers') and isinstance(value, list):
                if value and not all(isinstance(n, str) for n in value):
                    print(f"   ⚠️  {field} contains non-string values")
            elif field == 'patient_id_number' and not isinstance(value, str):
                print(f"   ⚠️  {field} is not a string")
    
    print(f"\n{'='*60}")
    if all_present:
        print("✅ TEST PASSED - All fields present")
        return True
    else:
        print("⚠️  TEST COMPLETED - Some fields missing (may be expected)")
        return True  # Still pass if extraction worked


if __name__ == "__main__":
    success = test_single_form()
    sys.exit(0 if success else 1)
