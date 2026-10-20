import fitz  # PyMuPDF

pdf1 = fitz.open('../reference/התחייבויות - דוגמאות, חלק 1 (PDF).pdf')
pdf2 = fitz.open('../reference/התחייבויות - דוגמאות, חלק 2 (PDF).pdf')

print(f'חלק 1: {len(pdf1)} עמודים')
print(f'חלק 2: {len(pdf2)} עמודים')
print(f'סה"כ: {len(pdf1) + len(pdf2)} טפסים')
print(f'\nכל טופס = עמוד אחד (בהנחה)')
