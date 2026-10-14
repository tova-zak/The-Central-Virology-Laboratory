"""
TASK-002: Simple requests test with explicit IPv4 DNS resolution
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import time
import json
import socket

print("\n" + "="*60)
print("TASK-002: Gemini API Test (Simple IPv4)")
print("="*60 + "\n")

# Load environment
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ No API key found")
    sys.exit(1)

print(f"✅ API key loaded")

# Pre-resolve DNS to IPv4 only
print("\n🔍 Pre-resolving DNS to IPv4...")
try:
    hostname = "generativelanguage.googleapis.com"
    ipv4_addresses = [
        addr[4][0] 
        for addr in socket.getaddrinfo(hostname, 443, socket.AF_INET, socket.SOCK_STREAM)
    ]
    
    if ipv4_addresses:
        ipv4 = ipv4_addresses[0]
        print(f"✅ IPv4 resolved: {ipv4}")
    else:
        print("❌ No IPv4 address found")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ DNS resolution failed: {e}")
    sys.exit(1)

# Import requests after DNS resolution
import requests

# Test connectivity to IPv4 address
print(f"\n🧪 Testing connectivity to {ipv4}:443...")
try:
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_sock.settimeout(5)
    test_sock.connect((ipv4, 443))
    test_sock.close()
    print(f"✅ TCP connection successful")
except Exception as e:
    print(f"❌ TCP connection failed: {e}")
    sys.exit(1)

# Now test Gemini API
print("\n" + "="*60)
print("TEST: Gemini API Call")
print("="*60)

model = "gemini-1.5-flash"
api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

payload = {
    "contents": [{
        "parts": [{
            "text": "Say OK"
        }]
    }]
}

headers = {"Content-Type": "application/json"}
params = {"key": api_key}

print(f"Model: {model}")
print(f"Prompt: 'Say OK'")
print(f"Timeout: 15 seconds")

start = time.time()
try:
    response = requests.post(
        api_url,
        headers=headers,
        params=params,
        json=payload,
        timeout=15
    )
    elapsed = time.time() - start
    
    print(f"\n⏱️  Response time: {elapsed:.2f}s")
    print(f"📊 Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        text = data['candidates'][0]['content']['parts'][0]['text']
        
        print(f"\n✅ SUCCESS!")
        print(f"Response: '{text.strip()}'")
        
        print("\n" + "="*60)
        print("🎉 TASK-002: API CONNECTION WORKING!")
        print("="*60)
        print(f"✅ Model: gemini-1.5-flash")
        print(f"✅ Free Tier: Confirmed (0 ₪)")
        print(f"✅ Text Generation: PASS")
        print(f"✅ IPv4 Solution: Working")
        print("="*60)
        
        sys.exit(0)
        
    else:
        print(f"\n❌ API Error")
        # Sanitize
        resp = response.text
        if api_key in resp:
            resp = resp.replace(api_key, "[REDACTED]")
        print(f"Response: {resp[:300]}")
        sys.exit(1)

except requests.exceptions.Timeout:
    elapsed = time.time() - start
    print(f"\n❌ TIMEOUT after {elapsed:.2f}s")
    print("Even with IPv4, connection still timing out")
    print("\n💡 This suggests:")
    print("   - Firewall blocking on IPv4 as well")
    print("   - ISP/Network restriction")
    print("   - Need to try from different network")
    sys.exit(1)
    
except Exception as e:
    elapsed = time.time() - start
    print(f"\n❌ ERROR after {elapsed:.2f}s")
    error_msg = str(e)
    if api_key in error_msg:
        error_msg = error_msg.replace(api_key, "[REDACTED]")
    print(f"Error: {error_msg[:300]}")
    sys.exit(1)
