"""
Combined solution: truststore + IPv4
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import time
import socket

print("\n" + "="*60)
print("Testing: truststore + IPv4 combination")
print("="*60 + "\n")

# Load environment
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ No API key")
    sys.exit(1)

print("✅ API key loaded")

# Imports
try:
    import truststore
    import ssl
    from google import genai
    print("✅ Packages imported")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

# Step 1: Inject truststore for SSL
print("\n🔧 Step 1: Injecting truststore...")
try:
    truststore.inject_into_ssl()
    print("✅ truststore injected into ssl")
except Exception as e:
    print(f"❌ truststore injection failed: {e}")
    sys.exit(1)

# Step 2: Force IPv4 at socket level
print("\n🔧 Step 2: Forcing IPv4...")
original_getaddrinfo = socket.getaddrinfo

def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Force IPv4 resolution"""
    return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = ipv4_getaddrinfo
print("✅ IPv4 forced at socket level")

# Step 3: Create client
print("\n🔧 Step 3: Creating genai.Client...")
try:
    client = genai.Client(api_key=api_key)
    print("✅ Client created")
except Exception as e:
    print(f"❌ Client creation failed: {e}")
    sys.exit(1)

# Step 4: Test API call
print("\n" + "="*60)
print("Testing Gemini API Call")
print("="*60)

model = "gemini-3.5-flash-lite"
print(f"\nModel: {model}")
print(f"Prompt: 'Say OK'")
print(f"Timeout: 20 seconds\n")

start = time.time()
try:
    response = client.models.generate_content(
        model=model,
        contents="Say OK"
    )
    elapsed = time.time() - start
    
    result = response.text.strip()
    
    print(f"✅ SUCCESS! ({elapsed:.2f}s)")
    print(f"Response: '{result}'")
    
    print("\n" + "="*60)
    print("🎉 PYTHON google-genai WORKING!")
    print("="*60)
    print(f"✅ Method: google-genai SDK")
    print(f"✅ SSL: truststore.inject_into_ssl()")
    print(f"✅ Network: IPv4 socket patch")
    print(f"✅ Time: {elapsed:.2f}s")
    print(f"✅ Model: {model}")
    print("="*60)
    
    # Restore socket
    socket.getaddrinfo = original_getaddrinfo
    
    sys.exit(0)
    
except Exception as e:
    elapsed = time.time() - start
    error_msg = str(e)
    
    print(f"❌ FAILED ({elapsed:.2f}s)")
    print(f"Error: {error_msg[:200]}")
    
    # Restore socket
    socket.getaddrinfo = original_getaddrinfo
    
    sys.exit(1)
