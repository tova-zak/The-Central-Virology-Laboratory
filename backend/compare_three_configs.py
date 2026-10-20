"""
Three-way comparison: A (V1 144dpi), B (V1 300dpi), C (V2 300dpi)
Configuration A uses existing results from validation_results.json
"""
import json
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.extraction.gemini_adapter import GeminiExtractor
from app.core.config import settings
import pymupdf
from PIL import Image
import io


def load_config_a_results() -> Optional[list]:
    """Load existing V1 144dpi results if available."""
    results_path = Path(__file__).parent.parent / 'tests' / 'validation_results.json'
    if results_path.exists():
        with open(results_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def extract_with_config(
    extractor: GeminiExtractor,
    pdf_path: Path,
    page_num: int,
    form_num: int,
    dpi: int,
    config_name: str
) -> Dict[str, Any]:
    """Extract a single form with specific configuration."""
    
    print(f"\n  🔹 {config_name} - מפיק תמונה ({dpi} DPI)...")
    
    try:
        # Convert PDF page to image
        doc = pymupdf.open(pdf_path)
        page = doc[page_num - 1]
        
        # Render at specified DPI
        pix = page.get_pixmap(dpi=dpi)
        img_data = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_data))
        
        doc.close()
        
        # Convert image to bytes
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        print(f"  🔹 {config_name} - שולח לGemini...")
        
        # Extract
        raw_result = extractor.extract(
            image=img_bytes,
            document_id=f"part2_page{page_num}_{config_name}",
            page_index=page_num - 1
        )
        
        fields = raw_result.fields
        
        print(f"  ✓ {config_name} הצליח ({raw_result.processing_time_ms:.0f}ms, {len(raw_result.warnings)} אזהרות)")
        
        return {
            'success': True,
            'fields': fields,
            'warnings': raw_result.warnings,
            'processing_time_ms': raw_result.processing_time_ms,
            'prompt_version': raw_result.prompt_version
        }
        
    except Exception as e:
        print(f"  ✗ {config_name} נכשל: {str(e)[:100]}")
        return {
            'success': False,
            'error': str(e)
        }


def format_value(value):
    """Format value for display."""
    if value is None:
        return "null"
    elif isinstance(value, list):
        if not value:
            return "[]"
        # Format list compactly
        if len(value) == 1:
            return f'["{value[0]}"]'
        return f'[{len(value)} items]'
    else:
        return f'"{value}"'


def print_comparison_table(all_results):
    """Print three-way comparison of all forms."""
    
    print(f"\n\n{'='*120}")
    print("השוואה משולשת: A (V1 144dpi) | B (V1 300dpi) | C (V2 300dpi)")
    print('='*120)
    
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
        config_a = result['config_a']
        config_b = result['config_b']
        config_c = result['config_c']
        
        print(f"\n{'─'*120}")
        print(f"טופס {form_num} (עמוד {result['page_num']})")
        print('─'*120)
        
        # Check for failures
        failures = []
        if not config_a['success']:
            failures.append("A")
        if not config_b['success']:
            failures.append("B")
        if not config_c['success']:
            failures.append("C")
        
        if failures:
            print(f"⚠️ תצורות שנכשלו: {', '.join(failures)}")
            for cfg_name, cfg_data in [('A', config_a), ('B', config_b), ('C', config_c)]:
                if not cfg_data['success']:
                    print(f"  {cfg_name}: {cfg_data.get('error', 'Unknown')[:80]}")
        
        # Print field comparison
        print(f"\n{'שדה':<25} {'A (V1 144dpi)':<30} {'B (V1 300dpi)':<30} {'C (V2 300dpi)':<30}")
        print('-'*120)
        
        for field_key, field_label in field_names:
            val_a = format_value(config_a['fields'].get(field_key)) if config_a['success'] else "---"
            val_b = format_value(config_b['fields'].get(field_key)) if config_b['success'] else "---"
            val_c = format_value(config_c['fields'].get(field_key)) if config_c['success'] else "---"
            
            # Highlight differences
            if val_a != val_b or val_b != val_c or val_a != val_c:
                marker = "⚡"
            else:
                marker = "  "
            
            print(f"{marker} {field_label:<23} {val_a:<30} {val_b:<30} {val_c:<30}")
        
        # Show warnings count
        print(f"\nאזהרות:")
        if config_a['success']:
            print(f"  A: {len(config_a['warnings'])} אזהרות")
        if config_b['success']:
            print(f"  B: {len(config_b['warnings'])} אזהרות")
        if config_c['success']:
            print(f"  C: {len(config_c['warnings'])} אזהרות")


def print_detailed_form(form_num, page_num, config_name, config_data):
    """Print detailed view of single configuration."""
    print(f"\n{'─'*100}")
    print(f"טופס {form_num} - תצורה {config_name}")
    print('─'*100)
    
    if not config_data['success']:
        print(f"❌ נכשל: {config_data.get('error', 'Unknown')}")
        return
    
    fields = config_data['fields']
    
    print(f"1. שם פרטי: {fields.get('patient_first_name') or 'null'}")
    print(f"2. שם משפחה: {fields.get('patient_last_name') or 'null'}")
    print(f"3. ת.ז: {fields.get('patient_id_number') or 'null'}")
    print(f"4. גורם שולח: {fields.get('sender') or 'null'}")
    print(f"5. תאריך קבלה: {fields.get('received_date') or 'null'}")
    print(f"6. מספרים מרכזיים: {fields.get('central_numbers') or '[]'}")
    print(f"7. מספרי התחייבות: {fields.get('commitment_numbers') or '[]'}")
    
    if config_data['warnings']:
        print(f"\nאזהרות ({len(config_data['warnings'])}):")
        for w in config_data['warnings']:
            print(f"  - {w}")


def main():
    print("="*120)
    print("השוואה משולשת של תצורות חילוץ")
    print("="*120)
    
    print("\nתצורות:")
    print("  A: V1.0 + 144 DPI (תוצאות קיימות)")
    print("  B: V1.0 + 300 DPI (חילוץ חדש)")
    print("  C: V2.0 + 300 DPI (פרומפט משופר)")
    
    # Load Config A (existing results)
    print("\n📁 טוען תוצאות תצורה A (קיימות)...")
    existing_results = load_config_a_results()
    
    if not existing_results:
        print("⚠️ לא נמצאו תוצאות קיימות, אתחל A מחדש")
        existing_results = [None] * 5
    else:
        print(f"✓ נטענו {len(existing_results)} תוצאות קיימות")
    
    # Initialize extractors for B and C
    print("\n🔧 מאתחל מנועי חילוץ...")
    
    extractor_v1 = GeminiExtractor(
        model=settings.gemini_model,
        prompt_version="1.0"
    )
    print("✓ Extractor V1.0 מוכן")
    
    extractor_v2 = GeminiExtractor(
        model=settings.gemini_model,
        prompt_version="2.0"
    )
    print("✓ Extractor V2.0 מוכן")
    
    pdf_path = Path(__file__).parent.parent / 'reference' / 'התחייבויות - דוגמאות, חלק 2 (PDF).pdf'
    
    print(f"\nקובץ מקור: {pdf_path.name}")
    print(f"מודל: {settings.gemini_model}")
    print(f"\n{'='*120}")
    print("מתחיל חילוץ...")
    print('='*120)
    
    all_results = []
    
    for i in range(1, 6):
        form_num = i
        page_num = i
        
        print(f"\nטופס {form_num} (עמוד {page_num})")
        print('─'*100)
        
        # Config A - use existing or extract
        if existing_results[i-1] and existing_results[i-1].get('success'):
            config_a_data = existing_results[i-1]
            # Convert old format to new format if needed
            if 'record' in config_a_data:
                rec = config_a_data['record']
                config_a = {
                    'success': True,
                    'fields': {
                        'patient_first_name': rec.get('first_name'),
                        'patient_last_name': rec.get('last_name'),
                        'patient_id_number': rec.get('id_number'),
                        'sender': rec.get('sending_entity'),
                        'received_date': rec.get('sample_receipt_date'),
                        'central_numbers': rec.get('central_numbers') or [],
                        'commitment_numbers': rec.get('commitment_numbers') or [],
                    },
                    'warnings': config_a_data.get('warnings', []),
                    'processing_time_ms': config_a_data.get('processing_time_ms', 0)
                }
            else:
                config_a = config_a_data
            print(f"  ✓ A (V1 144dpi) - שימוש בתוצאות קיימות")
        else:
            print(f"  ⚠️ A - אין תוצאות קיימות, מדלג")
            config_a = {'success': False, 'error': 'No existing results', 'fields': {},  'warnings': []}
        
        # Config B - V1 with 300 DPI
        config_b = extract_with_config(
            extractor_v1, pdf_path, page_num, form_num, dpi=300, config_name="B"
        )
        
        # Wait between requests
        time.sleep(3)
        
        # Config C - V2 with 300 DPI
        config_c = extract_with_config(
            extractor_v2, pdf_path, page_num, form_num, dpi=300, config_name="C"
        )
        
        all_results.append({
            'form_num': form_num,
            'page_num': page_num,
            'config_a': config_a,
            'config_b': config_b,
            'config_c': config_c
        })
        
        # Wait before next form
        if i < 5:
            print(f"\n  ⏱️  המתנה 4 שניות לפני הטופס הבא...")
            time.sleep(4)
    
    # Print comparison table
    print_comparison_table(all_results)
    
    # Print detailed views
    print(f"\n\n{'='*120}")
    print("פירוט מלא לכל תצורה")
    print('='*120)
    
    for result in all_results:
        for cfg_name, cfg_data in [('A', result['config_a']), ('B', result['config_b']), ('C', result['config_c'])]:
            print_detailed_form(result['form_num'], result['page_num'], cfg_name, cfg_data)
    
    # Save results
    output_path = Path(__file__).parent.parent / 'tests' / 'three_way_comparison.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n{'='*120}")
    print(f"תוצאות מלאות נשמרו ב: {output_path}")
    print(f"{'='*120}\n")


if __name__ == '__main__':
    main()
