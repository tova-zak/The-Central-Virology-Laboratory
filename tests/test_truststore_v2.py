"""
Test google-genai with truststore - v2
Try different http_options configurations
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import time

print("\n" + "="*60)
print("Testing google-genai with truststore (v2)")
print("="*60 + "\n")

# Load environment
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not found")
    sys.exit(1)

print("✅ API key loaded")

# Imports
try:
    import truststore
    import ssl
    import httpx
    from google import genai
    print("✅ All packages imported")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Create SSL context
ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
print("✅ SSL context created")

# Option 1: Try with verify parameter
print("\n📡 Option 1: http_options with verify...")
try:
    client = genai.Client(
        api_key=api_key,
        http_options={'verify': ssl_context}
    )
    print("✅ Client created with verify=ssl_context")
    
    # Test API call
    print("\nTesting API call...")
    start = time.time()
    
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Say OK"
    )
    elapsed = time.time() - start
    
    result = response.text.strip()
    
    print(f"\n🎉 SUCCESS! ({elapsed:.2f}s)")
    print(f"Response: '{result}'")
    print("\n" + "="*60)
    print("✅ PYTHON CONNECTION WORKING WITH TRUSTSTORE!")
    print("="*60)
    print(f"Method: google-genai with http_options={{'verify': ssl_context}}")
    print(f"SSL: truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)")
    print(f"Time: {elapsed:.2f}s")
    print("="*60)
    
    sys.exit(0)
    
except Exception as e:
    elapsed = time.time() - start if 'start' in locals() else 0
    print(f"❌ Failed ({elapsed:.2f}s): {str(e)[:200]}")

# Option 2: Try default (may use system SSL)
print("\n📡 Option 2: Default client (system SSL)...")
try:
    # Inject truststore globally
    truststore.inject_into_ssl()
    print("✅ truststore injected into ssl module globally")
    
    client = genai.Client(api_key=api_key)
    print("✅ Client created (default, with truststore injected)")
    
    # Test API call
    print("\nTesting API call...")
    start = time.time()
    
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Say OK"
    )
    elapsed = time.time() - start
    
    result = response.text.strip()
    
    print(f"\n🎉 SUCCESS! ({elapsed:.2f}s)")
    print(f"Response: '{result}'")
    print("\n" + "="*60)
    print("✅ PYTHON CONNECTION WORKING WITH TRUSTSTORE!")
    print("="*60)
    print(f"Method: truststore.inject_into_ssl() + default client")
    print(f"Time: {elapsed:.2f}s")
    print("="*60)
    
    sys.exit(0)
    
except Exception as e:
    elapsed = time.time() - start if 'start' in locals() else 0
    error_msg = str(e)
    
    print(f"❌ Failed ({elapsed:.2f}s)")
    print(f"Error: {error_msg[:200]}")
    
    if elapsed > 15:
        print("\n⚠️  Still timing out even with truststore.inject_into_ssl()")
    
    sys.exit(1)
