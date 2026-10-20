"""Create Golden Dataset from reference forms.

This script helps create manually-tagged ground truth data.
Each form is reviewed by human and tagged with correct values.
"""
import json
import fitz  # PyMuPDF
from pathlib import Path


def create_golden_dataset():
    """Create golden dataset structure."""
    
    # Reference PDFs
    pdf1_path = Path("../reference/התחייבויות - דוגמאות, חלק 1 (PDF).pdf")
    pdf2_path = Path("../reference/התחייבויות - דוגמאות, חלק 2 (PDF).pdf")
    
    # Select representative forms for golden dataset
    # Strategy: Mix of clear/unclear, printed/handwritten, Hebrew/English
    golden_forms = [
        # Development set (for prompt engineering, if needed)
        {"pdf": str(pdf1_path), "page": 0, "set": "dev", "notes": "First form - baseline"},
        {"pdf": str(pdf1_path), "page": 5, "set": "dev", "notes": "Different format"},
        {"pdf": str(pdf1_path), "page": 10, "set": "dev", "notes": "Handwritten elements"},
        {"pdf": str(pdf1_path), "page": 15, "set": "dev", "notes": "Multiple numbers"},
        {"pdf": str(pdf2_path), "page": 0, "set": "dev", "notes": "Part 2 sample"},
        {"pdf": str(pdf2_path), "page": 5, "set": "dev", "notes": "Different sender"},
        {"pdf": str(pdf2_path), "page": 10, "set": "dev", "notes": "Complex layout"},
        
        # Evaluation set (for final accuracy measurement)
        {"pdf": str(pdf1_path), "page": 3, "set": "eval", "notes": "Clear form"},
        {"pdf": str(pdf1_path), "page": 8, "set": "eval", "notes": "Partially unclear"},
        {"pdf": str(pdf1_path), "page": 13, "set": "eval", "notes": "Multiple commitments"},
        {"pdf": str(pdf1_path), "page": 18, "set": "eval", "notes": "Stamp/sticker"},
        {"pdf": str(pdf2_path), "page": 3, "set": "eval", "notes": "Part 2 eval 1"},
        {"pdf": str(pdf2_path), "page": 8, "set": "eval", "notes": "Part 2 eval 2"},
        {"pdf": str(pdf2_path), "page": 13, "set": "eval", "notes": "Part 2 eval 3"},
    ]
    
    dataset = {
        "version": "1.0",
        "created": "2026-10-14",
        "description": "Manually tagged ground truth for virology lab forms",
        "total_forms": len(golden_forms),
        "dev_set_count": len([f for f in golden_forms if f["set"] == "dev"]),
        "eval_set_count": len([f for f in golden_forms if f["set"] == "eval"]),
        "forms": []
    }
    
    print(f"Creating Golden Dataset with {len(golden_forms)} forms")
    print(f"Dev set: {dataset['dev_set_count']}")
    print(f"Eval set: {dataset['eval_set_count']}")
    print()
    
    # For each form, create template for manual tagging
    for i, form_spec in enumerate(golden_forms, 1):
        form_id = f"form_{i:03d}"
        
        # Template for manual ground truth
        ground_truth = {
            "form_id": form_id,
            "pdf_source": form_spec["pdf"],
            "page_index": form_spec["page"],
            "set": form_spec["set"],
            "notes": form_spec["notes"],
            "manually_tagged": False,  # Set to True after manual tagging
            "fields": {
                "patient_first_name": None,  # TODO: Fill manually
                "patient_last_name": None,   # TODO: Fill manually
                "patient_id_number": None,   # TODO: Fill manually (string with leading zeros)
                "sender": None,              # TODO: Fill manually
                "received_date": None,       # TODO: Fill manually (format: DD/MM/YYYY)
                "central_numbers": [],       # TODO: Fill manually (list of strings)
                "commitment_numbers": []     # TODO: Fill manually (list of strings)
            },
            "ground_truth_notes": ""  # Add notes about ambiguities, uncertainties
        }
        
        dataset["forms"].append(ground_truth)
        print(f"✓ Added {form_id}: {form_spec['notes']}")
    
    # Save template
    output_path = Path("../tests/fixtures/golden_dataset_template.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Template saved to: {output_path}")
    print(f"\n⚠️  NEXT STEP: Manually tag each form by reviewing the PDFs")
    print(f"   and filling in the 'fields' section with correct values.")
    print(f"   Set 'manually_tagged': true when done.")
    
    return dataset


if __name__ == "__main__":
    create_golden_dataset()
