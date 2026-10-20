"""Full Diagnostic Report - No API Calls

This script performs comprehensive diagnostics WITHOUT making any Gemini API calls.

It investigates:
1. Which .env file is actually being used
2. Effective GEMINI_MODEL value in three places
3. Environment variable overrides
4. Running Uvicorn processes
5. Python environment consistency
6. Timeout root cause (if possible to detect)
"""
import os
import sys
import subprocess
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

print("=" * 80)
print("FULL DIAGNOSTIC REPORT - NO API CALLS")
print("=" * 80)

# 1. Find all .env files
print("\n[1] LOCATE ALL .env FILES")
project_root = backend_dir.parent
env_files = list(project_root.rglob(".env"))
print(f"    Project root: {project_root}")
print(f"    Found {len(env_files)} .env file(s):")
for env_file in env_files:
    size = env_file.stat().st_size if env_file.exists() else 0
    print(f"      - {env_file.relative_to(project_root)} ({size} bytes)")

# 2. Check which .env is used by Pydantic Settings
print("\n[2] PYDANTIC SETTINGS .env PATH")
from dotenv import load_dotenv

# Load from expected location
expected_env = project_root / ".env"
print(f"    Expected: {expected_env}")
print(f"    Exists: {expected_env.exists()}")

if expected_env.exists():
    # Read raw file content
    with open(expected_env, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    gemini_model_line = [l.strip() for l in lines if l.startswith('GEMINI_MODEL=')]
    demo_mode_line = [l.strip() for l in lines if l.startswith('DEMO_MODE=')]
    
    print(f"    Raw GEMINI_MODEL in file: {gemini_model_line[0] if gemini_model_line else '[NOT FOUND]'}")
    print(f"    Raw DEMO_MODE in file: {demo_mode_line[0] if demo_mode_line else '[NOT FOUND]'}")

# 3. Check environment variables BEFORE loading .env
print("\n[3] ENVIRONMENT VARIABLES BEFORE .env LOAD")
gemini_model_before = os.environ.get('GEMINI_MODEL')
demo_mode_before = os.environ.get('DEMO_MODE')
print(f"    GEMINI_MODEL in os.environ: {repr(gemini_model_before)}")
print(f"    DEMO_MODE in os.environ: {repr(demo_mode_before)}")

if gemini_model_before:
    print(f"    ⚠️  WARNING: GEMINI_MODEL is already set in environment!")
    print(f"       This will OVERRIDE .env unless load_dotenv(override=True)")

# 4. Load .env with override and check again
print("\n[4] ENVIRONMENT VARIABLES AFTER .env LOAD (override=True)")
load_dotenv(expected_env, override=True)
gemini_model_after = os.environ.get('GEMINI_MODEL')
demo_mode_after = os.environ.get('DEMO_MODE')
print(f"    GEMINI_MODEL: {repr(gemini_model_after)}")
print(f"    DEMO_MODE: {repr(demo_mode_after)}")

# 5. Check Pydantic Settings object
print("\n[5] PYDANTIC SETTINGS OBJECT")
from app.core.config import settings

print(f"    settings.gemini_model: {repr(settings.gemini_model)}")
print(f"    settings.demo_mode: {repr(settings.demo_mode)}")
print(f"    settings.app_name: {repr(settings.app_name)}")

# Check where Pydantic loaded from
print(f"\n    Pydantic env_file config:")
if hasattr(settings, 'model_config'):
    config = settings.model_config
    if 'env_file' in config:
        print(f"      env_file: {config['env_file']}")

# 6. Check for running Uvicorn processes
print("\n[6] RUNNING UVICORN PROCESSES")
try:
    result = subprocess.run(
        ['powershell', '-Command', "Get-Process | Where-Object {$_.ProcessName -like '*python*' -or $_.ProcessName -like '*uvicorn*'} | Select-Object Id, ProcessName, StartTime"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if result.returncode == 0 and result.stdout.strip():
        print(f"    Found Python/Uvicorn processes:")
        print(f"{result.stdout}")
    else:
        print(f"    No Python/Uvicorn processes found (or query failed)")
except Exception as e:
    print(f"    ⚠️  Could not check processes: {e}")

# 7. Check Python environment
print("\n[7] PYTHON ENVIRONMENT")
print(f"    Python executable: {sys.executable}")
print(f"    Python version: {sys.version}")
print(f"    sys.path[0]: {sys.path[0]}")
print(f"    Working directory: {os.getcwd()}")

# 8. Test imports without API calls
print("\n[8] MODULE IMPORTS (No API calls)")
try:
    from app.services.extraction.gemini_adapter import GeminiExtractor
    print(f"    ✅ GeminiExtractor imported")
    
    from app.services.extraction.gemini_key_manager import get_key_manager
    key_manager = get_key_manager()
    print(f"    ✅ GeminiKeyManager: {len(key_manager._keys)} keys loaded")
    
    from app.services.extraction.quota_manager import get_quota_manager
    quota_manager = get_quota_manager()
    print(f"    ✅ QuotaManager imported")
    
    # Check QuotaManager attributes
    attrs = dir(quota_manager)
    relevant = [a for a in attrs if 'request' in a.lower() or 'quota' in a.lower() or 'limit' in a.lower()]
    print(f"    QuotaManager relevant attributes: {relevant}")
    
except Exception as e:
    print(f"    ❌ Import error: {e}")
    import traceback
    traceback.print_exc()

# 9. Analyze timeout scenario
print("\n[9] TIMEOUT SCENARIO ANALYSIS")
print("    Timeout occurred after 90 seconds in test_live_single_extraction.py")
print("    Possible causes:")
print("      1. Network timeout - no response from Gemini API")
print("      2. Invalid model name - API hung waiting for valid model")
print("      3. Authentication issue - hung on retry loop")
print("      4. Quota exhausted - circuit breaker in infinite wait")
print("      5. Code bug - infinite loop in quota/retry logic")
print("      6. DNS/SSL issue - couldn't reach api.generativeai.google.com")

# Check if we can reach Google API (just DNS, no actual request)
print("\n    Testing DNS resolution (no HTTP request):")
try:
    import socket
    ip = socket.gethostbyname('generativelanguage.googleapis.com')
    print(f"    ✅ DNS resolves: generativelanguage.googleapis.com -> {ip}")
except Exception as e:
    print(f"    ❌ DNS resolution failed: {e}")

# 10. Check gemini_adapter for timeout settings
print("\n[10] GEMINI_ADAPTER TIMEOUT CONFIGURATION")
try:
    import inspect
    from app.services.extraction.gemini_adapter import GeminiExtractor
    
    # Read source to find timeout settings
    source = inspect.getsource(GeminiExtractor)
    
    if 'timeout' in source.lower():
        print("    ✅ Timeout configured in GeminiExtractor")
        # Find timeout value
        import re
        timeout_matches = re.findall(r'timeout[=\s]*(\d+)', source, re.IGNORECASE)
        if timeout_matches:
            print(f"       Timeout values found: {timeout_matches}")
    else:
        print("    ⚠️  No explicit timeout found in GeminiExtractor")
        print("       May use default SDK timeout (unknown)")
    
    if 'retry' in source.lower():
        print("    ℹ️  Retry logic exists in GeminiExtractor")
        retry_matches = re.findall(r'max.*retry.*=.*(\d+)', source, re.IGNORECASE)
        if retry_matches:
            print(f"       Max retry values: {retry_matches}")
            
except Exception as e:
    print(f"    ⚠️  Could not analyze source: {e}")

# Final Summary
print("\n" + "=" * 80)
print("DIAGNOSTIC SUMMARY")
print("=" * 80)

issues = []
fixes = []

# Check consistency
if gemini_model_after != settings.gemini_model:
    issues.append(f"MISMATCH: env var '{gemini_model_after}' != settings '{settings.gemini_model}'")
    fixes.append("Restart Python process or use override=True in load_dotenv()")

if demo_mode_after != str(settings.demo_mode).lower():
    issues.append(f"MISMATCH: DEMO_MODE env '{demo_mode_after}' != settings '{settings.demo_mode}'")
    fixes.append("Ensure Pydantic Settings loads .env correctly")

if gemini_model_before and gemini_model_before != gemini_model_after:
    issues.append("Environment variable was overridden by .env")
    fixes.append("Clear PowerShell env vars: $env:GEMINI_MODEL = $null")

if issues:
    print("\n❌ ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"   {i}. {issue}")
    
    print("\n🔧 FIXES REQUIRED:")
    for i, fix in enumerate(fixes, 1):
        print(f"   {i}. {fix}")
else:
    print("\n✅ No configuration mismatches detected")

print("\n📋 EFFECTIVE CONFIGURATION:")
print(f"   .env file: {expected_env}")
print(f"   GEMINI_MODEL: {settings.gemini_model}")
print(f"   DEMO_MODE: {settings.demo_mode}")
print(f"   Extractor type: {'MockExtractor' if settings.demo_mode else 'GeminiExtractor'}")
print(f"   API keys loaded: {len(key_manager._keys) if 'key_manager' in locals() else 'unknown'}")

print("\n⚠️  TIMEOUT ROOT CAUSE:")
print("   Cannot determine without making actual API call")
print("   Likely causes based on symptoms:")
print("     - Model 'gemini-3.8-flash' may not exist or be unavailable")
print("     - Authentication issue with API keys")
print("     - Network/DNS issue")
print("     - SDK bug with this model name")
print("\n   Next step: Try a known-good model name (e.g., gemini-1.5-pro)")
print("   or check Google AI Studio for valid model names")

print("=" * 80)
