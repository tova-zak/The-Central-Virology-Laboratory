"""Debug script to verify configuration loading.

This script verifies that:
1. .env file is loaded correctly
2. DEMO_MODE is read as expected
3. Correct extractor is selected
4. Gemini API keys are loaded
5. Model name is correct
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load .env explicitly
from dotenv import load_dotenv
env_path = backend_dir.parent / ".env"
load_dotenv(env_path)

print("=" * 80)
print("CONFIGURATION DEBUG REPORT")
print("=" * 80)

# Check .env file
print(f"\n[1] .env FILE LOCATION")
print(f"    Path: {env_path}")
print(f"    Exists: {env_path.exists()}")

# Check raw environment variables
print(f"\n[2] RAW ENVIRONMENT VARIABLES")
demo_mode_raw = os.getenv("DEMO_MODE")
hybrid_enabled_raw = os.getenv("HYBRID_ENGINE_ENABLED")
gemini_model_raw = os.getenv("GEMINI_MODEL")
gemini_key_raw = os.getenv("GEMINI_API_KEY", "")

print(f"    DEMO_MODE (raw): '{demo_mode_raw}' (type: {type(demo_mode_raw)})")
print(f"    HYBRID_ENGINE_ENABLED (raw): '{hybrid_enabled_raw}'")
print(f"    GEMINI_MODEL (raw): '{gemini_model_raw}'")
print(f"    GEMINI_API_KEY: {'[SET]' if gemini_key_raw else '[NOT SET]'} (length: {len(gemini_key_raw)})")

# Check numbered API keys
api_keys = []
for i in range(1, 10):
    key = os.getenv(f"GEMINI_API_{i}")
    if key:
        api_keys.append(f"GEMINI_API_{i}")

print(f"    Numbered API keys found: {len(api_keys)} ({', '.join(api_keys)})")

total_keys = len(api_keys)

# Import config and check parsed values
print(f"\n[3] PARSED CONFIGURATION (Pydantic Settings)")
from app.core.config import settings

print(f"    settings.demo_mode: {settings.demo_mode} (type: {type(settings.demo_mode)})")
print(f"    settings.hybrid_engine_enabled: {settings.hybrid_engine_enabled}")
print(f"    settings.gemini_model: {settings.gemini_model}")
print(f"    settings.gemini_api_key: {'[SET]' if settings.gemini_api_key else '[NOT SET]'}")

# Check extractor selection logic
print(f"\n[4] EXTRACTOR SELECTION")
if settings.demo_mode:
    print(f"    ❌ DEMO MODE ACTIVE")
    print(f"    Selected extractor: MockExtractor")
    print(f"    ⚠️  WARNING: All extractions will return mock data!")
else:
    print(f"    ✅ LIVE MODE ACTIVE")
    print(f"    Selected extractor: GeminiExtractor")
    print(f"    Model: {settings.gemini_model}")

# Test GeminiKeyManager
print(f"\n[5] GEMINI KEY MANAGER")
try:
    from app.services.extraction.gemini_key_manager import GeminiKeyManager
    
    key_manager = GeminiKeyManager()
    manager_keys = len(key_manager._keys)
    current_key = key_manager.get_next_key()
    
    print(f"    Total keys loaded: {manager_keys}")
    print(f"    Current key index: {key_manager._current_index}")
    print(f"    Current key (first 10 chars): {current_key[:10] if current_key else '[NONE]'}...")
    
    if manager_keys == 0:
        print(f"    ❌ ERROR: No API keys loaded!")
    elif manager_keys < 9:
        print(f"    ⚠️  WARNING: Expected 9 keys, found {manager_keys}")
    else:
        print(f"    ✅ All keys loaded successfully")
        
except Exception as e:
    print(f"    ❌ ERROR loading GeminiKeyManager: {e}")
    manager_keys = 0

# Test QuotaManager
print(f"\n[6] QUOTA MANAGER")
try:
    from app.services.extraction.quota_manager import get_quota_manager
    
    quota_manager = get_quota_manager()
    # QuotaManager doesn't have can_make_request, check circuit breaker instead
    is_open = quota_manager.circuit_breaker_open
    
    print(f"    Circuit breaker open: {is_open}")
    if is_open:
        print(f"    ❌ Circuit breaker is open (quota exhausted)")
    else:
        print(f"    ✅ Ready to make Gemini API calls")
        
    # Check limits
    print(f"    Rate limits: {quota_manager.requests_per_minute} RPM, {quota_manager.requests_per_day} RPD")
    
except Exception as e:
    print(f"    ❌ ERROR loading QuotaManager: {e}")

# Final recommendation
print(f"\n[7] FINAL STATUS")
print("=" * 80)

if settings.demo_mode:
    print("❌ ISSUE: DEMO_MODE=true in .env")
    print("   The system will use MockExtractor and return fake data.")
    print("   To use real Gemini extraction, set DEMO_MODE=false in .env")
elif not settings.gemini_api_key and len(api_keys) == 0:
    print("❌ ISSUE: No Gemini API keys configured")
    print("   Add GEMINI_API_KEY or GEMINI_API_1-9 to .env")
elif settings.gemini_model not in ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash-exp"]:
    print(f"⚠️  WARNING: Unknown model '{settings.gemini_model}'")
    print("   Free tier models: gemini-1.5-flash, gemini-1.5-pro")
else:
    print("✅ CONFIGURATION OK")
    print(f"   Ready for LIVE Gemini extraction with {settings.gemini_model}")
    print(f"   Using {manager_keys if 'manager_keys' in locals() else len(api_keys)} API keys in round-robin")

print("=" * 80)
