"""
Analyze Part 2 PDF to identify first 5 forms
"""
import pymupdf
from pathlib import Path

pdf_path = Path(__file__).parent.parent / 'reference' / 'התחייבויות - דוגמאות, חלק 2 (PDF).pdf'

doc = pymupdf.open(pdf_path)
print(f"PDF: {pdf_path.name}")
print(f"Total pages: {len(doc)}")
print("\n" + "="*80)

# Analyze each page
for page_num in range(len(doc)):
    page = doc[page_num]
    text = page.get_text()
    
    print(f"\nPage {page_num + 1}")
    print("-" * 40)
    
    # Look for form indicators
    lines = text.split('\n')[:30]  # First 30 lines
    
    # Check for ID number pattern
    for line in lines:
        if 'ת.ז' in line or 'תעודת זהות' in line:
            print(f"  ID field found: {line.strip()}")
        if 'מרכזי' in line:
            print(f"  Central number: {line.strip()}")
        if 'התחייבות' in line or 'דרישה' in line:
            print(f"  Commitment/Request: {line.strip()}")
    
    print()

doc.close()
