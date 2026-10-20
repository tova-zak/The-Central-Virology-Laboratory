#!/usr/bin/env python3
"""Test script to upload a PDF and create a batch."""
import requests
from pathlib import Path

pdf_path = Path("reference/התחייבויות - דוגמאות, חלק 1 (PDF).pdf")

if not pdf_path.exists():
    print(f"Error: PDF not found at {pdf_path}")
    exit(1)

print(f"Uploading {pdf_path.name} ({pdf_path.stat().st_size} bytes)...")

with open(pdf_path, 'rb') as f:
    files = {'files': (pdf_path.name, f, 'application/pdf')}
    response = requests.post('http://localhost:8000/api/batches', files=files)

if response.status_code == 201:
    data = response.json()
    print(f"✅ Success! Batch created:")
    print(f"  Batch ID: {data['batch_id']}")
    print(f"  Documents: {len(data['documents'])}")
    for doc in data['documents']:
        print(f"    - {doc['filename']} (ID: {doc['document_id']}, Pages: {doc['page_count']})")
else:
    print(f"❌ Error {response.status_code}: {response.text}")
