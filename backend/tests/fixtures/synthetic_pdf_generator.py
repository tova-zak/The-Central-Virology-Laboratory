"""
Synthetic PDF generator for E2E testing.
Creates deterministic test PDFs with known ground truth.

NO REAL PATIENT DATA - synthetic names and IDs only.
"""
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from pathlib import Path
import fitz  # PyMuPDF


def create_synthetic_page(
    page_num: int,
    patient_name: str,
    patient_id: str,
    central_number: str,
    commitment_number: str,
    sender: str,
    date: str,
    page_notation: str = ""  # e.g., "עמוד 1/2"
) -> bytes:
    """Create a single synthetic form page as PNG.
    
    Returns PNG image bytes with Hebrew text content.
    """
    img = Image.new('RGB', (800, 1100), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to load Hebrew-capable font
    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
        font_small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 18)
    except:
        # Fallback to default if Arial not found
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw form content (RTL layout for Hebrew)
    y = 50
    
    if page_notation:
        draw.text((400, y), page_notation, fill='black', font=font_large)
        y += 40
    
    draw.text((50, y), f"מספר זהות: {patient_id}", fill='black', font=font_small)
    y += 40
    
    draw.text((50, y), f"שם מטופל: {patient_name}", fill='black', font=font_small)
    y += 40
    
    draw.text((50, y), f"מספר מרכזי: {central_number}", fill='black', font=font_small)
    y += 40
    
    draw.text((50, y), f"התחייבות: {commitment_number}", fill='black', font=font_small)
    y += 40
    
    draw.text((50, y), f"גורם שולח: {sender}", fill='black', font=font_small)
    y += 40
    
    draw.text((50, y), f"תאריך קבלה: {date}", fill='black', font=font_small)
    
    # Convert to PNG bytes
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()


def create_synthetic_pdf(pages: list[dict], output_path: Path) -> Path:
    """Create multi-page PDF from page definitions.
    
    Args:
        pages: List of dicts with keys: patient_name, patient_id, central_number,
               commitment_number, sender, date, page_notation
        output_path: Where to save PDF
    
    Returns:
        Path to created PDF
    """
    pdf_doc = fitz.open()  # Create new PDF
    
    for i, page_data in enumerate(pages):
        # Generate PNG for this page
        png_bytes = create_synthetic_page(
            page_num=i,
            patient_name=page_data.get("patient_name", "דוד כהן"),
            patient_id=page_data.get("patient_id", "123456789"),
            central_number=page_data.get("central_number", f"C{i:03d}"),
            commitment_number=page_data.get("commitment_number", f"H{i:03d}"),
            sender=page_data.get("sender", "לאומית"),
            date=page_data.get("date", "14/10/2026"),
            page_notation=page_data.get("page_notation", "")
        )
        
        # Convert PNG to PDF page
        img_pdf = fitz.open(stream=png_bytes, filetype="png")
        pdf_doc.insert_pdf(img_pdf)
        img_pdf.close()
    
    # Save PDF
    pdf_doc.save(output_path)
    pdf_doc.close()
    
    return output_path


# Ground truth for 10-page test PDF
SYNTHETIC_10PAGE_GROUND_TRUTH = {
    "total_pages": 10,
    "total_forms": 8,  # 6 single-page + 1 two-page form + 1 multi-commitment
    "total_commitments": 10,
    "pages": [
        # Single-page forms (pages 0-5)
        {"patient_name": "דוד כהן", "patient_id": "123456789", "central_number": "C001", "commitment_number": "H001", "sender": "לאומית", "date": "14/10/2026"},
        {"patient_name": "שרה לוי", "patient_id": "987654321", "central_number": "C002", "commitment_number": "H002", "sender": "כללית", "date": "14/10/2026"},
        {"patient_name": "מרים אביב", "patient_id": "111222333", "central_number": "C003", "commitment_number": "H003", "sender": "מכבי", "date": "14/10/2026"},
        {"patient_name": "יוסף חדש", "patient_id": "444555666", "central_number": "C004", "commitment_number": "H004", "sender": "מאוחדת", "date": "14/10/2026"},
        {"patient_name": "רחל ישן", "patient_id": "777888999", "central_number": "C005", "commitment_number": "H005", "sender": "לאומית", "date": "14/10/2026"},
        {"patient_name": "אברהם גדול", "patient_id": "000111222", "central_number": "C006", "commitment_number": "H006", "sender": "כללית", "date": "14/10/2026"},
        
        # Two-page form (pages 6-7) - tests multi-page segmentation
        {"patient_name": "יעקב קטן", "patient_id": "333444555", "central_number": "C007", "commitment_number": "H007", "sender": "מכבי", "date": "14/10/2026", "page_notation": "עמוד 1/2"},
        {"patient_name": "יעקב קטן", "patient_id": "333444555", "central_number": "C007", "commitment_number": "H008", "sender": "מכבי", "date": "14/10/2026", "page_notation": "עמוד 2/2"},
        
        # Form with 2 commitments (page 8) - tests multiple commitments per form
        {"patient_name": "לאה כבירה", "patient_id": "666777888", "central_number": "C008", "commitment_number": "H009,H010", "sender": "לאומית", "date": "14/10/2026"},
        
        # Form with "דגימה" field (page 9) - Leumit context (commitment detection test)
        {"patient_name": "בנימין זעיר", "patient_id": "999000111", "central_number": "C009", "commitment_number": "דגימה", "sender": "לאומית", "date": "14/10/2026"},
    ]
}


if __name__ == "__main__":
    # Generate test PDF for manual inspection
    output = Path("test_10page_synthetic.pdf")
    create_synthetic_pdf(SYNTHETIC_10PAGE_GROUND_TRUTH["pages"], output)
    print(f"Created: {output}")
    print(f"Pages: {SYNTHETIC_10PAGE_GROUND_TRUTH['total_pages']}")
    print(f"Expected forms: {SYNTHETIC_10PAGE_GROUND_TRUTH['total_forms']}")
    print(f"Expected commitments: {SYNTHETIC_10PAGE_GROUND_TRUTH['total_commitments']}")
