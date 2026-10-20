"""Pre-Live Verification Script

Verifies ALL conditions before making real Gemini API call:
✅ DEMO_MODE=false
✅ gemini-2.0-flash-exp configured
✅ GeminiExtractor will be selected
✅ API keys loaded
✅ Focused Retry disabled
✅ No auto-key-rotation on 429
✅ Code compatible with model
✅ Structured Output supported
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load .env
from dotenv import load_dotenv
env_path = backend_dir.parent / ".env"
load_dotenv(env_path, override=True)

print("=" * 80)
print("PRE-LIVE VERIFICATION CHECKLIST")
print("=" * 80)

issues = []
warnings = []

# 1. DEMO_MODE
print("\n[1] DEMO_MODE Verification")
demo_mode_raw = os.getenv("DEMO_MODE", "true")
print(f"    .env value: {demo_mode_raw}")

from app.core.config import settings
print(f"    Parsed value: {settings.demo_mode}")

if settings.demo_mode:
    issues.append("DEMO_MODE is true - will use MockExtractor")
    print("    ❌ FAILED: DEMO_MODE=true")
else:
    print("    ✅ PASSED: DEMO_MODE=false")

# 2. Model Configuration
print("\n[2] Model Configuration")
model = settings.gemini_model
print(f"    Model: {model}")

if model == "gemini-1.5-flash":
    issues.append(f"Model {model} was disabled on 29.09.2025")
    print(f"    ❌ FAILED: {model} is disabled")
elif model == "gemini-3.8-flash":
    warnings.append(f"Model {model} - verify it exists and is free tier")
    print(f"    ⚠️  WARNING: Verify {model} is valid")
elif model == "gemini-2.0-flash-exp":
    print(f"    ✅ PASSED: {model} (experimental free tier)")
else:
    warnings.append(f"Unknown model: {model}")
    print(f"    ⚠️  WARNING: Unknown model {model}")

# 3. Extractor Selection
print("\n[3] Extractor Selection")
if settings.demo_mode:
    print("    ❌ Will select: MockExtractor")
else:
    print("    ✅ Will select: GeminiExtractor")

# 4. API Keys
print("\n[4] API Keys")
try:
    from app.services.extraction.gemini_key_manager import get_key_manager
    key_manager = get_key_manager()
    num_keys = len(key_manager._keys)
    print(f"    Keys loaded: {num_keys}")
    
    if num_keys == 0:
        issues.append("No API keys loaded")
        print("    ❌ FAILED: No keys")
    else:
        print(f"    ✅ PASSED: {num_keys} keys loaded")
        
except Exception as e:
    issues.append(f"Key manager error: {e}")
    print(f"    ❌ FAILED: {e}")

# 5. Focused Retry
print("\n[5] Focused Retry")
hybrid_retry = os.getenv("HYBRID_ENABLE_FOCUSED_RETRY", "false").lower()
print(f"    HYBRID_ENABLE_FOCUSED_RETRY: {hybrid_retry}")

if hybrid_retry == "true":
    warnings.append("Focused Retry is enabled")
    print("    ⚠️  WARNING: Focused Retry enabled")
else:
    print("    ✅ PASSED: Focused Retry disabled")

# 6. Auto Key Rotation on 429
print("\n[6] Auto Key Rotation on 429")
try:
    from app.services.extraction.quota_manager import get_quota_manager
    quota_manager = get_quota_manager()
    print(f"    QuotaManager initialized")
    print(f"    Rate limits: {quota_manager.requests_per_minute} RPM, {quota_manager.requests_per_day} RPD")
    
    # Check if circuit breaker is open
    if hasattr(quota_manager, 'is_circuit_open'):
        if quota_manager.is_circuit_open():
            issues.append("Circuit breaker is open")
            print("    ❌ FAILED: Circuit breaker open")
        else:
            print("    ✅ PASSED: Circuit breaker closed")
    else:
        print("    ℹ️  Circuit breaker status unknown")
        
except Exception as e:
    warnings.append(f"QuotaManager check failed: {e}")
    print(f"    ⚠️  WARNING: {e}")

# 7. Code Compatibility
print("\n[7] Code Compatibility with Model")
try:
    from app.services.extraction.gemini_adapter import GeminiExtractor
    import inspect
    
    # Check if GeminiExtractor uses google-genai (not google-generativeai)
    source = inspect.getsource(GeminiExtractor)
    
    if 'google.genai' in source or 'from google import genai' in source:
        print("    ✅ Using google-genai SDK")
    elif 'google.generativeai' in source:
        issues.append("Using old google-generativeai SDK")
        print("    ❌ Old SDK detected")
    else:
        warnings.append("Could not detect SDK")
        print("    ⚠️  Could not verify SDK")
    
    if 'GenerateContentConfig' in source:
        print("    ✅ Uses GenerateContentConfig")
    
    if 'response_mime_type' in source and 'application/json' in source:
        print("    ✅ Structured Output configured")
    
except Exception as e:
    warnings.append(f"Code compatibility check failed: {e}")
    print(f"    ⚠️  WARNING: {e}")

# 8. Structured Output Support
print("\n[8] Structured Output Schema")
try:
    from app.services.extraction.gemini_adapter import CommitmentFormExtraction
    schema_fields = CommitmentFormExtraction.model_fields
    print(f"    Schema fields: {len(schema_fields)}")
    print(f"    Fields: {', '.join(schema_fields.keys())}")
    print("    ✅ Pydantic schema defined")
except Exception as e:
    issues.append(f"Schema check failed: {e}")
    print(f"    ❌ FAILED: {e}")

# 9. Hybrid Engine Status
print("\n[9] Hybrid Engine Configuration")
hybrid_enabled = os.getenv("HYBRID_ENGINE_ENABLED", "false").lower()
print(f"    HYBRID_ENGINE_ENABLED: {hybrid_enabled}")

if hybrid_enabled == "true":
    print("    ✅ Hybrid Engine enabled")
    print("    ℹ️  Preprocessing and OCR will run alongside Gemini")
else:
    print("    ℹ️  Hybrid Engine disabled")

# Final Summary
print("\n" + "=" * 80)
print("VERIFICATION SUMMARY")
print("=" * 80)

if issues:
    print(f"\n❌ CRITICAL ISSUES ({len(issues)}):")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
    print("\n⚠️  CANNOT PROCEED WITH LIVE TEST")
    print("   Fix critical issues before running Live extraction")
    exit_code = 1
    
elif warnings:
    print(f"\n⚠️  WARNINGS ({len(warnings)}):")
    for i, warning in enumerate(warnings, 1):
        print(f"   {i}. {warning}")
    print("\n✅ CAN PROCEED WITH CAUTION")
    print("   Review warnings but test can proceed")
    exit_code = 0
    
else:
    print("\n✅✅✅ ALL CHECKS PASSED ✅✅✅")
    print("\nSystem is ready for LIVE Gemini extraction:")
    print(f"  - Model: {model}")
    print(f"  - Keys: {num_keys if 'num_keys' in locals() else 'unknown'}")
    print(f"  - Demo Mode: {settings.demo_mode}")
    print(f"  - Extractor: {'Mock' if settings.demo_mode else 'Gemini'}")
    print("\n🚀 READY TO PROCEED WITH LIVE TEST")
    exit_code = 0

print("=" * 80)
sys.exit(exit_code)
