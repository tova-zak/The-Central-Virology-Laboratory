"""Semi-automated tagging of golden dataset.

Uses Gemini to extract initial values, then requires manual verification.
This is NOT just copying Gemini output - it's using AI to assist human review.
"""
import json
import fitz  # PyMuPDF
from pathlib import Path
import time

from app.services.extraction.gemini_adapter import GeminiExtractor
from app.core.config import settings


def pdf_page_to_image(pdf_path: str, page_num: int) -> bytes:
    """Convert PDF page to PNG."""
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    pix = page.get_pixmap(dpi=300)
    img_bytes = pix.tobytes("png")
    doc.close()
    return img_bytes


def tag_forms():
    """Tag forms with Gemini assistance."""
    
    # Load template
    template_path = Path("../tests/fixtures/golden_dataset_template.json")
    with open(template_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    # Initialize extractor
    extractor = GeminiExtractor(
        model=settings.gemini_model
    )
    
    print(f"Tagging {len(dataset['forms'])} forms...")
    print(f"WARNING: This is AI-ASSISTED tagging, not ground truth yet!")
    print()
    
    # Process each form
    for form in dataset['forms']:
        form_id = form['form_id']
        pdf_path = form['pdf_source']
        page_idx = form['page_index']
        
        print(f"Processing {form_id} (page {page_idx})...")
        
        try:
            # Convert to image
            image_bytes = pdf_page_to_image(pdf_path, page_idx)
            
            # Extract
            result = extractor.extract(
                image=image_bytes,
                document_id=form_id,
                page_index=page_idx
            )
            
            # Store Gemini extraction (as initial values for manual review)
            form['gemini_extraction'] = result.fields
            form['gemini_warnings'] = result.warnings
            form['gemini_processing_time_ms'] = result.processing_time_ms
            
            print(f"  ✓ Extracted in {result.processing_time_ms:.0f}ms")
            if result.warnings:
                print(f"  WARNING: {len(result.warnings)} warnings")
            
            # Wait to respect rate limits
            time.sleep(1)
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            form['gemini_extraction'] = None
            form['error'] = str(e)
    
    # Save with Gemini extractions
    output_path = Path("../tests/fixtures/golden_dataset_gemini_assisted.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Gemini-assisted extractions saved to: {output_path}")
    print(f"\nIMPORTANT: These are NOT ground truth yet!")
    print(f"   Manual review required to create final golden_dataset.json")
    print(f"   Compare Gemini output with actual forms and correct errors.")


if __name__ == "__main__":
    tag_forms()
