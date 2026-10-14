"""
Test google-genai with truststore for SSL
Based on user's successful truststore verification
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import time

print("\n" + "="*60)
print("Testing google-genai with truststore")
print("="*60 + "\n")

# Load environment
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not found in .env")
    sys.exit(1)

print("✅ API key loaded from .env")

# Import truststore
try:
    import truststore
    import ssl
    print("✅ truststore imported")
except ImportError as e:
    print(f"❌ truststore not available: {e}")
    print("   Run: pip install truststore")
    sys.exit(1)

# Import httpx
try:
    import httpx
    print("✅ httpx imported")
except ImportError:
    print("❌ httpx not available")
    sys.exit(1)

# Import google-genai
try:
    from google import genai
    print("✅ google-genai imported")
except ImportError as e:
    print(f"❌ google-genai not available: {e}")
    sys.exit(1)

# Create SSL context with truststore
print("\n🔧 Creating truststore SSL context...")
try:
    ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    print("✅ SSL context created")
except Exception as e:
    print(f"❌ Failed to create SSL context: {e}")
    sys.exit(1)

# Create httpx client with truststore SSL context
print("\n🔧 Creating httpx client with truststore...")
try:
    http_client = httpx.Client(
        verify=ssl_context,
        timeout=20.0
    )
    print("✅ httpx client created with truststore SSL")
except Exception as e:
    print(f"❌ Failed to create httpx client: {e}")
    sys.exit(1)

# Try to create genai.Client with custom http client
print("\n🔧 Attempting to configure google-genai with custom httpx client...")

try:
    # Check if genai.Client supports http_options
    import inspect
    sig = inspect.signature(genai.Client.__init__)
    params = list(sig.parameters.keys())
    print(f"   genai.Client parameters: {params}")
    
    supports_http_options = 'http_options' in params
    
    if supports_http_options:
        print("   ✅ http_options parameter found")
        
        # Try to pass custom client
        client = genai.Client(
            api_key=api_key,
            http_options={'client': http_client}
        )
        print("✅ genai.Client created with custom http_options")
        
    else:
        print("   ⚠️  http_options not found in genai.Client parameters")
        print("   Trying default client (may timeout)...")
        
        client = genai.Client(api_key=api_key)
        print("✅ genai.Client created (default)")
        
except Exception as e:
    print(f"❌ Failed to create genai.Client: {e}")
    sys.exit(1)

# Test API call
print("\n" + "="*60)
print("Testing Gemini API Call")
print("="*60)

model = "gemini-3.5-flash-lite"
prompt = "Say hello"

print(f"\nModel: {model}")
print(f"Prompt: '{prompt}'")
print(f"Timeout: 20 seconds\n")

start = time.time()
try:
    response = client.models.generate_content(
        model=model,
        contents=prompt
    )
    elapsed = time.time() - start
    
    result_text = response.text.strip()
    
    print(f"✅ SUCCESS! ({elapsed:.2f}s)")
    print(f"Response: '{result_text}'")
    
    print("\n" + "="*60)
    print("🎉 PYTHON CONNECTION WORKING!")
    print("="*60)
    print(f"✅ Method: google-genai SDK")
    print(f"✅ SSL: truststore.SSLContext")
    print(f"✅ Time: {elapsed:.2f}s")
    print(f"✅ Model: {model}")
    print("="*60)
    
    sys.exit(0)
    
except Exception as e:
    elapsed = time.time() - start
    error_msg = str(e)
    
    print(f"❌ FAILED ({elapsed:.2f}s)")
    print(f"Error type: {type(e).__name__}")
    print(f"Error: {error_msg[:200]}")
    
    if elapsed > 15:
        print("\n🔍 Diagnosis: Still timing out despite truststore")
        print("   Possible causes:")
        print("   - google-genai not using provided httpx client")
        print("   - Different SSL issue")
    elif "SSL" in error_msg or "certificate" in error_msg:
        print("\n🔍 Diagnosis: SSL error despite truststore")
        print("   truststore may not be compatible with google-genai")
    
    sys.exit(1)

finally:
    # Clean up
    if 'http_client' in locals():
        http_client.close()
