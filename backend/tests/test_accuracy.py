"""Accuracy measurement on golden dataset with real Gemini API.

This test measures actual extraction accuracy against manually verified ground truth.
"""
import json
import fitz  # PyMuPDF
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

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


def calculate_field_accuracy(expected, extracted):
    """Calculate accuracy for a single field.
    
    Returns:
        tuple: (correct, total, details)
    """
    # Handle uncertain ground truth
    if expected == "uncertain":
        return (None, 1, "uncertain_ground_truth")
    
    # Handle None/missing
    if expected is None and extracted is None:
        return (1, 1, "both_missing")
    if expected is None and extracted is not None:
        return (0, 1, "false_extraction")
    if expected is not None and extracted is None:
        return (0, 1, "missed_extraction")
    
    # Handle lists
    if isinstance(expected, list) and isinstance(extracted, list):
        if set(expected) == set(extracted):
            return (1, 1, "list_exact_match")
        else:
            # Partial credit: intersection / union
            if not expected and not extracted:
                return (1, 1, "both_empty_lists")
            expected_set = set(expected)
            extracted_set = set(extracted)
            if not expected_set and not extracted_set:
                return (1, 1, "both_empty")
            intersection = len(expected_set & extracted_set)
            union = len(expected_set | extracted_set)
            return (intersection / union, 1, f"list_partial_{intersection}/{union}")
    
    # Handle strings
    if isinstance(expected, str) and isinstance(extracted, str):
        if expected.lower().strip() == extracted.lower().strip():
            return (1, 1, "string_match")
        else:
            return (0, 1, "string_mismatch")
    
    # Type mismatch
    return (0, 1, "type_mismatch")


def measure_accuracy():
    """Measure extraction accuracy on golden dataset."""
    
    print("="*70)
    print("ACCURACY MEASUREMENT - Real Gemini API")
    print("="*70)
    
    # Load golden dataset
    golden_path = Path("../tests/fixtures/golden_dataset.json")
    with open(golden_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    
    print(f"\nDataset: {dataset['description']}")
    print(f"Forms to evaluate: {dataset['eval_set_count']}")
    print()
    
    # Initialize extractor
    extractor = GeminiExtractor(
        model=settings.gemini_model
    )
    
    # Track metrics per field
    field_names = [
        'patient_first_name',
        'patient_last_name',
        'patient_id_number',
        'sender',
        'received_date',
        'central_numbers',
        'commitment_numbers'
    ]
    
    field_stats = {fname: {"correct": 0, "total": 0, "uncertain": 0} for fname in field_names}
    
    results = []
    
    # Process each form
    for i, form in enumerate(dataset['forms'], 1):
        form_id = form['form_id']
        pdf_path = Path(__file__).parent.parent / form['pdf_source']
        page_idx = form['page_index']
        expected = form['expected_fields']
        
        print(f"[{i}/{dataset['eval_set_count']}] {form_id}: {form['notes']}")
        
        try:
            # Extract
            image_bytes = pdf_page_to_image(str(pdf_path), page_idx)
            result = extractor.extract(image_bytes, form_id, page_idx)
            extracted = result.fields
            
            # Compare each field
            form_result = {
                "form_id": form_id,
                "notes": form['notes'],
                "fields": {}
            }
            
            for field_name in field_names:
                exp_value = expected.get(field_name)
                ext_value = extracted.get(field_name)
                
                correct, total, detail = calculate_field_accuracy(exp_value, ext_value)
                
                if correct is None:
                    field_stats[field_name]["uncertain"] += 1
                    status = "UNCERTAIN"
                elif correct == 1:
                    field_stats[field_name]["correct"] += correct
                    field_stats[field_name]["total"] += total
                    status = "CORRECT"
                else:
                    field_stats[field_name]["correct"] += correct
                    field_stats[field_name]["total"] += total
                    status = f"WRONG ({detail})"
                
                form_result["fields"][field_name] = {
                    "expected": exp_value,
                    "extracted": ext_value,
                    "status": status,
                    "detail": detail
                }
                
                print(f"  {field_name}: {status}")
            
            results.append(form_result)
            print()
            
            # Rate limit
            import time
            time.sleep(2)
            
        except Exception as e:
            print(f"  ERROR: {e}")
            print()
            results.append({
                "form_id": form_id,
                "error": str(e)
            })
    
    # Calculate overall accuracy
    print("="*70)
    print("ACCURACY RESULTS")
    print("="*70)
    print()
    
    for field_name in field_names:
        stats = field_stats[field_name]
        if stats["total"] > 0:
            accuracy = (stats["correct"] / stats["total"]) * 100
            print(f"{field_name:25s}: {accuracy:5.1f}% ({stats['correct']:.1f}/{stats['total']}) [uncertain: {stats['uncertain']}]")
        else:
            print(f"{field_name:25s}: N/A (all uncertain)")
    
    # Overall
    total_correct = sum(s["correct"] for s in field_stats.values())
    total_fields = sum(s["total"] for s in field_stats.values())
    if total_fields > 0:
        overall = (total_correct / total_fields) * 100
        print()
        print(f"{'OVERALL':25s}: {overall:5.1f}% ({total_correct:.1f}/{total_fields})")
    
    # Save results
    output_path = Path("../tests/accuracy_report.json")
    report = {
        "dataset_version": dataset["version"],
        "model": settings.gemini_model,
        "forms_tested": len([r for r in results if "error" not in r]),
        "forms_failed": len([r for r in results if "error" in r]),
        "field_stats": field_stats,
        "overall_accuracy": overall if total_fields > 0 else None,
        "detailed_results": results
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\nDetailed results saved to: {output_path}")
    print("="*70)


if __name__ == "__main__":
    measure_accuracy()
