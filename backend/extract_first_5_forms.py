"""
Extract first 5 forms from Part 2 using GeminiExtractor
"""
import json
import sys
import time
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.extraction.gemini_adapter import GeminiExtractor
from app.core.config import settings
import pymupdf
from PIL import Image
import io

def extract_form(extractor, pdf_path: Path, page_num: int, form_num: int):
    """Extract a single form from a specific page"""
    print(f"\n{'='*80}")
    print(f"טופס {form_num} - עמוד {page_num}")
    print('='*80)
    
    try:
        # Open PDF and convert page to image
        doc = pymupdf.open(pdf_path)
        page = doc[page_num - 1]  # 0-indexed
        
        # Render page as image
        pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2))  # 2x resolution
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        doc.close()
        
        # Extract using Gemini (synchronous call)
        print(f"שולח לGemini...")
        
        # Convert image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        # Call extract
        raw_result = extractor.extract(
            image=img_bytes,
            document_id=f"part2_page{page_num}",
            page_index=page_num - 1
        )
        
        # Parse fields from raw_result
        fields = raw_result.fields
        
        # Display results
        print(f"\nתוצאות חילוץ:")
        print(f"זמן עיבוד: {raw_result.processing_time_ms:.0f}ms")
        
        print(f"\n1. שם פרטי: {fields.get('patient_first_name') or 'חסר'}")
        print(f"2. שם משפחה: {fields.get('patient_last_name') or 'חסר'}")
        print(f"3. ת.ז: {fields.get('patient_id_number') or 'חסר'}")
        print(f"4. מספר מרכזי: {fields.get('central_numbers') or 'חסר'}")
        print(f"5. תאריך קבלת דגימה: {fields.get('received_date') or 'חסר'}")
        print(f"6. גורם שולח: {fields.get('sender') or 'חסר'}")
        print(f"7. מספר התחייבות: {fields.get('commitment_numbers') or 'חסר'}")
        
        if raw_result.warnings:
            print(f"\nאזהרות:")
            for warning in raw_result.warnings:
                print(f"  - {warning}")
        
        return {
            'form_num': form_num,
            'page_num': page_num,
            'success': True,
            'record': {
                'first_name': fields.get('patient_first_name'),
                'last_name': fields.get('patient_last_name'),
                'id_number': fields.get('patient_id_number'),
                'central_numbers': fields.get('central_numbers'),
                'sample_receipt_date': fields.get('received_date'),
                'sending_entity': fields.get('sender'),
                'commitment_numbers': fields.get('commitment_numbers'),
            },
            'warnings': raw_result.warnings,
            'processing_time_ms': raw_result.processing_time_ms
        }
        
    except Exception as e:
        print(f"שגיאה: {str(e)}")
        return {
            'form_num': form_num,
            'page_num': page_num,
            'success': False,
            'error': str(e)
        }

def main():
    # Initialize extractor
    extractor = GeminiExtractor(
        model=settings.gemini_model  # Use configured model
    )
    
    pdf_path = Path(__file__).parent.parent / 'reference' / 'התחייבויות - דוגמאות, חלק 2 (PDF).pdf'
    
    print(f"קובץ מקור: {pdf_path.name}")
    print(f"מחלץ את 5 הטפסים הראשונים...")
    
    # Extract first 5 forms
    # Assuming each form is on a separate page (pages 1-5)
    results = []
    for i in range(1, 6):
        result = extract_form(extractor, pdf_path, page_num=i, form_num=i)
        results.append(result)
        
        # Wait between requests to avoid rate limiting
        if i < 5:
            print(f"\nממתין 3 שניות לפני הטופס הבא...")
            time.sleep(3)
    
    # Summary table
    print(f"\n\n{'='*80}")
    print("סיכום תוצאות")
    print('='*80)
    print(f"\n{'טופס':<8} {'עמוד':<8} {'שם פרטי':<15} {'שם משפחה':<15} {'ת.ז':<12} {'סטטוס'}")
    print('-'*80)
    
    for r in results:
        if r['success'] and r['record']:
            rec = r['record']
            print(f"{r['form_num']:<8} {r['page_num']:<8} {(rec['first_name'] or 'חסר'):<15} {(rec['last_name'] or 'חסר'):<15} {(rec['id_number'] or 'חסר'):<12} הצליח")
        else:
            print(f"{r['form_num']:<8} {r['page_num']:<8} {'--':<15} {'--':<15} {'--':<12} נכשל")
    
    # Save raw results
    output_path = Path(__file__).parent.parent / 'tests' / 'validation_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\nתוצאות מלאות נשמרו ב: {output_path}")

if __name__ == '__main__':
    main()
