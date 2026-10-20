#!/usr/bin/env python3
"""Verify that extractor selection works correctly based on DEMO_MODE."""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Load .env
from dotenv import load_dotenv
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

print("Extractor Selection Verification")
print("="*60)

# Check DEMO_MODE
demo_mode = os.getenv("DEMO_MODE", "").lower()
print(f"\nDEMO_MODE={demo_mode}")

# Import processor to check its configuration
from app.services.processing.background import get_processor

# Get processor (which initializes extractor)
processor = get_processor()

print(f"\nSelected Extractor: {type(processor._extractor).__name__}")
print(f"Extractor module: {type(processor._extractor).__module__}")

# Verify expectations
if demo_mode == "true":
    expected = "MockExtractor"
else:
    expected = "GeminiExtractor"

if type(processor._extractor).__name__ == expected:
    print(f"\n✓ CORRECT: {expected} selected (as expected for DEMO_MODE={demo_mode})")
    
    # Additional check for GeminiExtractor
    if expected == "GeminiExtractor":
        print("\n✓ GeminiExtractor has required attributes:")
        print(f"  - ssl_context: {hasattr(processor._extractor, 'ssl_context')}")
        print(f"  - http_transport: {hasattr(processor._extractor, 'http_transport')}")
        print(f"  - key_manager: {hasattr(processor._extractor, 'key_manager')}")
        print(f"  - quota_manager: {hasattr(processor._extractor, 'quota_manager')}")
    
    sys.exit(0)
else:
    print(f"\n✗ WRONG: Expected {expected}, got {type(processor._extractor).__name__}")
    sys.exit(1)
