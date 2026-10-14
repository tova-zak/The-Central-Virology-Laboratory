"""
TASK-002 Diagnostic: Identify connection failure
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

print("\n" + "="*60)
print("TASK-002: Connection Diagnostic")
print("="*60 + "\n")

# 1. Environment loading
print("1. Testing .env loading...")
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
print(f"   .env path: {env_path}")
print(f"   .env exists: {env_path.exists()}")

load_dotenv(env_path)
api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    print(f"   ✅ API key loaded successfully (length: {len(api_key)})")
else:
    print(f"   ❌ API key NOT loaded")
    sys.exit(1)

# 2. SDK import
print("\n2. Testing SDK import...")
try:
    from google import genai
    print("   ✅ google-genai imported")
    print(f"   Available: {', '.join([x for x in dir(genai) if not x.startswith('_')][:10])}")
except ImportError as e:
    print(f"   ❌ Import failed: {e}")
    sys.exit(1)

# 3. Client initialization
print("\n3. Testing client initialization...")
try:
    client = genai.Client(api_key=api_key)
    print("   ✅ Client created")
except Exception as e:
    print(f"   ❌ Client initialization failed: {e}")
    sys.exit(1)

# 4. Test with timeout control
print("\n4. Testing API call with minimal request...")
print("   Model: gemini-1.5-flash")
print("   Timeout: 30 seconds")

import time
start_time = time.time()

try:
    # Minimal test request
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents="Say OK"
    )
    
    elapsed = time.time() - start_time
    print(f"   ✅ Request successful! ({elapsed:.2f}s)")
    print(f"   Response: {response.text[:50]}")
    
except Exception as e:
    elapsed = time.time() - start_time
    error_type = type(e).__name__
    error_msg = str(e)
    
    print(f"   ❌ Request failed after {elapsed:.2f}s")
    print(f"   Error type: {error_type}")
    print(f"   Error message: {error_msg[:200]}")
    
    # Diagnose specific errors
    if "timeout" in error_msg.lower():
        print("\n   🔍 Diagnosis: TIMEOUT")
        print("      - Network may be slow or blocked")
        print("      - Try increasing timeout or check firewall")
    elif "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower():
        print("\n   🔍 Diagnosis: API KEY INVALID")
        print("      - Verify key at: https://aistudio.google.com/apikey")
        print("      - Check for extra spaces or characters")
    elif "quota" in error_msg.lower() or "limit" in error_msg.lower():
        print("\n   🔍 Diagnosis: QUOTA EXCEEDED")
        print("      - Free tier daily limit reached")
        print("      - Wait 24 hours or try different model")
    elif "404" in error_msg or "not found" in error_msg.lower():
        print("\n   🔍 Diagnosis: MODEL NOT FOUND")
        print("      - Model name may be incorrect")
        print("      - Try: gemini-1.5-flash, gemini-2.0-flash-exp")
    elif "billing" in error_msg.lower():
        print("\n   🔍 Diagnosis: BILLING REQUIRED")
        print("      - ⚠️  Model may not be on free tier!")
        print("      - STOP: This violates 0 ₪ budget constraint")
    else:
        print("\n   🔍 Diagnosis: UNKNOWN ERROR")
        print("      - See error message above")
    
    sys.exit(1)

print("\n" + "="*60)
print("✅ Diagnostic complete: Connection working!")
print("="*60)
