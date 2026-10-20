"""Test Hebrew OCR to check RTL handling."""
import io
import os
from PIL import Image, ImageDraw, ImageFont

os.environ["TESSERACT_CMD"] = "D:\\Users\\1\\tesseract.exe"

import pytesseract
pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")

from app.services.ocr.tesseract_extractor import TesseractExtractor, OCRConfig


def create_test_image_hebrew():
    """Create image with Hebrew text for RTL testing."""
    img = Image.new('RGB', (600, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try Arial font
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 32)
    except:
        font = ImageFont.load_default()
    
    y = 50
    
    # Hebrew with number
    draw.text((50, y), "שם: דוד כהן", fill='black', font=font)
    y += 50
    
    # ID with label
    draw.text((50, y), "ת.ז: 123456789", fill='black', font=font)
    y += 50
    
    # Central number
    draw.text((50, y), "מרכזי: 654321", fill='black', font=font)
    y += 50
    
    # Mixed Hebrew+English
    draw.text((50, y), "Name: David Cohen", fill='black', font=font)
    y += 50
    
    # Number with leading zeros
    draw.text((50, y), "מספר: 00789456", fill='black', font=font)
    
    return img


def test_hebrew_ocr():
    """Test OCR on Hebrew text."""
    print("=" * 70)
    print("Testing Hebrew OCR - RTL Handling")
    print("=" * 70)
    
    # Create test image
    img = create_test_image_hebrew()
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()
    
    # Initialize OCR
    config = OCRConfig(
        languages=["heb", "eng"],
        min_confidence=60.0,
        tesseract_cmd=os.getenv("TESSERACT_CMD")
    )
    extractor = TesseractExtractor(config=config)
    
    # Extract
    result = extractor.extract(
        image=img_bytes,
        document_id="hebrew-test",
        page_index=0
    )
    
    print(f"\nProcessing Time: {result.processing_time_ms:.0f}ms")
    print(f"\n{'='*70}")
    print("Raw OCR Text (as returned by Tesseract):")
    print("=" * 70)
    print(result.raw_response)
    print()
    
    # Analyze each line
    lines = result.raw_response.split('\n')
    print("=" * 70)
    print("Line-by-Line Analysis:")
    print("=" * 70)
    
    for i, line in enumerate(lines, 1):
        if line.strip():
            print(f"Line {i}: '{line}'")
            
            # Check for Hebrew characters
            has_hebrew = any('\u0590' <= c <= '\u05FF' for c in line)
            has_numbers = any(c.isdigit() for c in line)
            has_english = any(c.isascii() and c.isalpha() for c in line)
            
            print(f"  Hebrew: {has_hebrew}, Numbers: {has_numbers}, English: {has_english}")
            
            # Show character codes for Hebrew
            if has_hebrew:
                hebrew_chars = [c for c in line if '\u0590' <= c <= '\u05FF']
                print(f"  Hebrew chars: {' '.join(hex(ord(c)) for c in hebrew_chars[:5])}")
            print()
    
    # Test extracted fields
    print("=" * 70)
    print("Parsed Fields:")
    print("=" * 70)
    print(f"patient_id_number: {result.fields.get('patient_id_number')}")
    print(f"central_numbers: {result.fields.get('central_numbers')}")
    print()
    
    # Get bounding boxes
    blocks = extractor.get_text_blocks(img_bytes)
    print("=" * 70)
    print(f"Text Blocks with Bounding Boxes ({len(blocks)} total):")
    print("=" * 70)
    
    for i, block in enumerate(blocks[:10], 1):
        text = block['text']
        conf = block['confidence']
        has_hebrew = any('\u0590' <= c <= '\u05FF' for c in text)
        
        print(f"{i}. '{text}' (conf: {conf:.0f}%) [Hebrew: {has_hebrew}]")
    
    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)
    print("\nConclusions:")
    print("1. If Hebrew appears reversed, it's an RTL display issue")
    print("2. Character codes should be correct (0x05XX range)")
    print("3. Number extraction should work regardless of Hebrew")
    print("=" * 70)


if __name__ == "__main__":
    test_hebrew_ocr()
