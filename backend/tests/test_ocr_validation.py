"""OCR validation tests with real Tesseract (not Mock).

Tests that Tesseract can extract Hebrew and English text from images.
"""
import io
import os
import pytest
from PIL import Image, ImageDraw, ImageFont

# CRITICAL: Set Tesseract path BEFORE importing any app modules
# This must happen before pytesseract is imported by any of our code
if os.getenv("TESSERACT_CMD"):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")

from app.services.ocr.tesseract_extractor import TesseractExtractor, OCRConfig, MockOCRExtractor


# Skip all tests if TESSERACT_CMD not set or Tesseract not available
def is_tesseract_available():
    """Check if Tesseract is available."""
    is_available, _ = TesseractExtractor.check_tesseract_available()
    return is_available


# Mark all tests to skip if Tesseract not available
pytestmark = pytest.mark.skipif(
    not is_tesseract_available(),
    reason="Tesseract OCR not installed or TESSERACT_CMD not set"
)


def create_synthetic_test_image() -> bytes:
    """Create a synthetic test image with Hebrew and English text.
    
    Returns:
        PNG image bytes
    """
    # Create white background
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a font that supports Hebrew
    # If not available, use default (will show as boxes for Hebrew)
    try:
        # Try common Hebrew font paths
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf"
        ]
        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, 40)
                break
        
        if font is None:
            # Fallback to default
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Draw text lines
    y = 50
    
    # Line 1: Hebrew label with ID number
    draw.text((50, y), "ת.ז: 123456789", fill='black', font=font)
    y += 60
    
    # Line 2: Date in Hebrew
    draw.text((50, y), "התקבל: 15/03/2024", fill='black', font=font)
    y += 60
    
    # Line 3: Central number
    draw.text((50, y), "מרכזי: 654321", fill='black', font=font)
    y += 60
    
    # Line 4: Commitment number
    draw.text((50, y), "התחייבות: ABC123", fill='black', font=font)
    y += 60
    
    # Line 5: English text
    draw.text((50, y), "Patient Name: John Doe", fill='black', font=font)
    y += 60
    
    # Line 6: Mixed Hebrew and numbers
    draw.text((50, y), "דגימה 789456", fill='black', font=font)
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    return img_bytes.getvalue()


def test_tesseract_initialization():
    """Test that Tesseract initializes successfully."""
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
    
    config = OCRConfig(
        languages=["heb", "eng"],
        min_confidence=70.0,
        tesseract_cmd=os.getenv("TESSERACT_CMD")
    )
    
    extractor = TesseractExtractor(config=config)
    
    # Should not raise error
    assert extractor is not None
    assert extractor.config.languages == ["heb", "eng"]


def test_tesseract_extract_synthetic_image():
    """Test OCR extraction on synthetic image."""
    config = OCRConfig(
        languages=["heb", "eng"],
        min_confidence=60.0,  # Lower for synthetic text
        tesseract_cmd=os.getenv("TESSERACT_CMD")
    )
    
    extractor = TesseractExtractor(config=config)
    
    # Create test image
    image_bytes = create_synthetic_test_image()
    
    # Extract
    result = extractor.extract(
        image=image_bytes,
        document_id="synthetic-test-001",
        page_index=0
    )
    
    # Check result structure
    assert result.schema_version == "1.0"
    assert result.model_id == "tesseract-ocr"
    assert result.prompt_version == "ocr-verification-v1"
    assert result.processing_time_ms > 0
    
    # Check warnings
    assert len(result.warnings) > 0
    assert any("OCR_NOTE" in w for w in result.warnings)
    
    # Check raw response contains some text
    assert result.raw_response is not None
    assert len(result.raw_response) > 10
    
    print(f"\n=== OCR Extraction Result ===")
    print(f"Processing Time: {result.processing_time_ms:.0f}ms")
    print(f"Model: {result.model_id}")
    print(f"\nExtracted Fields:")
    print(f"  patient_id_number: {result.fields.get('patient_id_number')}")
    print(f"  received_date: {result.fields.get('received_date')}")
    print(f"  central_numbers: {result.fields.get('central_numbers')}")
    print(f"  commitment_numbers: {result.fields.get('commitment_numbers')}")
    print(f"\nRaw Text (first 500 chars):")
    print(result.raw_response[:500])


def test_tesseract_extract_numbers():
    """Test that OCR can extract ID number from synthetic image."""
    config = OCRConfig(
        languages=["heb", "eng"],
        min_confidence=60.0,
        tesseract_cmd=os.getenv("TESSERACT_CMD")
    )
    
    extractor = TesseractExtractor(config=config)
    image_bytes = create_synthetic_test_image()
    
    result = extractor.extract(
        image=image_bytes,
        document_id="synthetic-test-002",
        page_index=0
    )
    
    # Check if ID number was extracted (might not be perfect)
    # Tesseract should at least find SOME digits
    raw_text = result.raw_response.lower()
    
    # Check for presence of digits (even if not perfectly parsed)
    has_digits = any(char.isdigit() for char in raw_text)
    assert has_digits, "OCR should extract at least some digits"
    
    print(f"\n=== Number Extraction Test ===")
    print(f"ID extracted: {result.fields.get('patient_id_number')}")
    print(f"Raw text contains digits: {has_digits}")


def test_tesseract_get_text_blocks():
    """Test bounding box extraction."""
    config = OCRConfig(
        languages=["heb", "eng"],
        extract_bboxes=True,
        tesseract_cmd=os.getenv("TESSERACT_CMD")
    )
    
    extractor = TesseractExtractor(config=config)
    image_bytes = create_synthetic_test_image()
    
    blocks = extractor.get_text_blocks(image_bytes)
    
    # Should extract at least some text blocks
    assert len(blocks) > 0
    
    # Check structure of first block
    if blocks:
        block = blocks[0]
        assert "bbox" in block
        assert "text" in block
        assert "confidence" in block
        
        # bbox should be tuple (x, y, w, h)
        assert len(block["bbox"]) == 4
        assert all(isinstance(v, int) for v in block["bbox"])
        
        print(f"\n=== Text Blocks Extracted ===")
        print(f"Total blocks: {len(blocks)}")
        print(f"First 5 blocks:")
        for i, block in enumerate(blocks[:5]):
            print(f"  Block {i+1}: '{block['text']}' @ {block['bbox']} (conf: {block['confidence']:.1f}%)")


def test_mock_ocr_extractor():
    """Test MockOCRExtractor (no real Tesseract needed)."""
    extractor = MockOCRExtractor()
    
    # Create dummy image
    img = Image.new('RGB', (100, 100), color='white')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    
    result = extractor.extract(
        image=img_bytes.getvalue(),
        document_id="mock-test-001",
        page_index=0
    )
    
    # Check structure
    assert result.schema_version == "1.0"
    assert result.model_id == "mock-ocr"
    assert result.prompt_version == "mock-v1"
    
    # Check that all fields are None/[]
    assert result.fields["patient_id_number"] is None
    assert result.fields["central_numbers"] == []
    
    # Check warnings indicate mock
    assert any("MOCK_OCR" in w for w in result.warnings)


def test_tesseract_check_available():
    """Test the static availability check."""
    is_available, error_msg = TesseractExtractor.check_tesseract_available()
    
    # Should be available (since test suite is running)
    assert is_available is True
    assert error_msg is None


if __name__ == "__main__":
    # Run with: python -m pytest backend/tests/test_ocr_validation.py -v -s
    pytest.main([__file__, "-v", "-s"])
