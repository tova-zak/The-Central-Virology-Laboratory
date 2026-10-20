"""
Compare V1.0 vs V2.0 prompt performance on first 5 forms from Part 2
"""
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.extraction.gemini_adapter import GeminiExtractor
from app.core.config import settings
import pymupdf
from PIL import Image
import io


def extract_form_with_version(
    extractor_v1: GeminiExtractor,
    extractor_v2: GeminiExtractor,
    pdf_path: Path,
    page_num: int,
    form_num: int
) -> Dict[str, Any]:
    """Extract a single form with both prompt versions."""
    
    print(f"\n{'='*80}")
    print(f"טופס {form_num} - עמוד {page_num}")
    print('='*80)
    
    # Convert PDF page to image (same for both versions)
    doc = pymupdf.open(pdf_path)
    page = doc[page_num - 1]
    
    # Render at 300 DPI for better OCR (fixing the resolution issue)
    pix = page.get_pixmap(dpi=300)
    img_data = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_data))
    
    doc.close()
    
    # Convert image to bytes
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()
    
    results = {
        'form_num': form_num,
        'page_num': page_num,
        'v1': None,
        'v2': None
    }
    
    # Extract with V1.0
    print(f"\n🔵 גרסה 1.0 - שולח לGemini...")
    try:
        raw_result_v1 = extractor_v1.extract(
            image=img_bytes,
            document_id=f"part2_page{page_num}_v1",
            page_index=page_num - 1
        )
        
        fields_v1 = raw_result_v1.fields
        
        print(f"✓ הצליח ({raw_result_v1.processing_time_ms:.0f}ms)")
        print(f"  אזהרות: {len(raw_result_v1.warnings)}")
        
        results['v1'] = {
            'success': True,
            'fields': fields_v1,
            'warnings': raw_result_v1.warnings,
            'processing_time_ms': raw_result_v1.processing_time_ms
        }
        
    except Exception as e:
        print(f"✗ נכשל: {str(e)}")
        results['v1'] = {
            'success': False,
            'error': str(e)
        }
    
    # Wait between requests
    print(f"\nהמתנה 3 שניות...")
    time.sleep(3)
    
    # Extract with V2.0
    print(f"\n🟢 גרסה 2.0 - שולח לGemini...")
    try:
        raw_result_v2 = extractor_v2.extract(
            image=img_bytes,
            document_id=f"part2_page{page_num}_v2",
            page_index=page_num - 1
        )
        
        fields_v2 = raw_result_v2.fields
        
        print(f"✓ הצליח ({raw_result_v2.processing_time_ms:.0f}ms)")
        print(f"  אזהרות: {len(raw_result_v2.warnings)}")
        
        results['v2'] = {
            'success': True,
            'fields': fields_v2,
            'warnings': raw_result_v2.warnings,
            'processing_time_ms': raw_result_v2.processing_time_ms
        }
        
    except Exception as e:
        print(f"✗ נכשל: {str(e)}")
        results['v2'] = {
            'success': False,
            'error': str(e)
        }
    
    return results


def format_value(value):
    """Format value for display."""
    if value is None:
        return "חסר"
    elif isinstance(value, list):
        if not value:
            return "[]"
        return str(value)
    else:
        return str(value)


def print_comparison_table(all_results):
    """Print side-by-side comparison of all forms."""
    
    print(f"\n\n{'='*100}")
    print("השוואת תוצאות: גרסה 1.0 לעומת גרסה 2.0")
    print('='*100)
    
    field_names = [
        ('patient_first_name', 'שם פרטי'),
        ('patient_last_name', 'שם משפחה'),
        ('patient_id_number', 'ת.ז'),
        ('sender', 'גורם שולח'),
        ('received_date', 'תאריך קבלה'),
        ('central_numbers', 'מספרים מרכזיים'),
        ('commitment_numbers', 'מספרי התחייבות')
    ]
    
    for result in all_results:
        form_num = result['form_num']
        v1 = result['v1']
        v2 = result['v2']
        
        print(f"\n{'─'*100}")
        print(f"טופס {form_num} (עמוד {result['page_num']})")
        print('─'*100)
        
        if not v1['success'] or not v2['success']:
            print("⚠️ אחת הגרסאות נכשלה")
            if not v1['success']:
                print(f"  V1.0 שגיאה: {v1.get('error', 'Unknown')}")
            if not v2['success']:
                print(f"  V2.0 שגיאה: {v2.get('error', 'Unknown')}")
            continue
        
        # Compare each field
        print(f"\n{'שדה':<25} {'V1.0':<35} {'V2.0':<35}")
        print('-'*100)
        
        for field_key, field_label in field_names:
            v1_val = format_value(v1['fields'].get(field_key))
            v2_val = format_value(v2['fields'].get(field_key))
            
            # Highlight differences
            if v1_val != v2_val:
                marker = "⚡"
            else:
                marker = "  "
            
            print(f"{marker} {field_label:<23} {v1_val:<35} {v2_val:<35}")
        
        # Show warnings
        print(f"\nאזהרות V1.0 ({len(v1['warnings'])}):")
        if v1['warnings']:
            for w in v1['warnings']:
                print(f"  - {w}")
        else:
            print("  (אין)")
        
        print(f"\nאזהרות V2.0 ({len(v2['warnings'])}):")
        if v2['warnings']:
            for w in v2['warnings']:
                print(f"  - {w}")
        else:
            print("  (אין)")


def main():
    print("="*100)
    print("השוואת גרסאות פרומפט: V1.0 (מקורי) vs V2.0 (משופר)")
    print("="*100)
    
    # Initialize both extractors
    print("\nמאתחל מנועי חילוץ...")
    extractor_v1 = GeminiExtractor(
        model=settings.gemini_model,
        prompt_version="1.0"
    )
    print("✓ V1.0 מוכן")
    
    extractor_v2 = GeminiExtractor(
        model=settings.gemini_model,
        prompt_version="2.0"
    )
    print("✓ V2.0 מוכן")
    
    pdf_path = Path(__file__).parent.parent / 'reference' / 'התחייבויות - דוגמאות, חלק 2 (PDF).pdf'
    
    print(f"\nקובץ מקור: {pdf_path.name}")
    print(f"מודל: {settings.gemini_model}")
    print(f"רזולוציה: 300 DPI")
    print(f"\nמחלץ 5 טפסים עם שתי גרסאות הפרומפט...")
    
    all_results = []
    
    for i in range(1, 6):
        result = extract_form_with_version(
            extractor_v1, extractor_v2, pdf_path, page_num=i, form_num=i
        )
        all_results.append(result)
        
        # Wait between forms
        if i < 5:
            print(f"\n{'─'*80}")
            print(f"ממתין 4 שניות לפני הטופס הבא...")
            time.sleep(4)
    
    # Print comparison table
    print_comparison_table(all_results)
    
    # Save detailed results
    output_path = Path(__file__).parent.parent / 'tests' / 'prompt_comparison_results.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n{'='*100}")
    print(f"תוצאות מלאות נשמרו ב: {output_path}")
    print('='*100)


if __name__ == '__main__':
    main()
