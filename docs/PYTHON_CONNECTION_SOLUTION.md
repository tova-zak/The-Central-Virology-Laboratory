# Python google-genai Connection Solution

**Date:** October 14, 2026  
**Status:** ✅ WORKING  
**Test Result:** 3.87s response time

---

## Problem Summary

Python's `google-genai` SDK experienced timeout issues (60+ seconds) due to:
1. IPv6 connection attempts failing
2. SSL certificate verification issues

---

## ✅ Working Solution

### Requirements
```bash
pip install google-genai truststore
```

### Implementation

```python
import os
import socket
import truststore
from google import genai
from dotenv import load_dotenv

# Load API key securely
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Step 1: Fix SSL with Windows certificate store
truststore.inject_into_ssl()

# Step 2: Force IPv4 (temporary patch for this process only)
original_getaddrinfo = socket.getaddrinfo

def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Force IPv4 address resolution"""
    return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = ipv4_getaddrinfo

try:
    # Step 3: Use google-genai SDK normally
    client = genai.Client(api_key=api_key)
    
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents="Your prompt here"
    )
    
    result = response.text
    print(result)
    
finally:
    # Step 4: Clean up - restore original socket behavior
    socket.getaddrinfo = original_getaddrinfo
```

---

## Why This Works

### truststore
- Uses Windows Certificate Store instead of certifi bundle
- Resolves SSL/TLS certificate verification issues
- Safe: doesn't disable verification, uses system trust

### IPv4 Socket Patch
- Forces DNS resolution to IPv4 addresses only
- Bypasses IPv6 timeout issues
- Scoped: only affects current Python process
- Reversible: restored after use

---

## For FastAPI Integration (TASK-005+)

### Approach 1: Application Startup (Recommended)

```python
# app/main.py
from fastapi import FastAPI
import truststore
import socket

# Apply patches at application startup
truststore.inject_into_ssl()

original_getaddrinfo = socket.getaddrinfo

def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = ipv4_getaddrinfo

app = FastAPI()

# Your routes here...
```

**Note:** Socket patch affects entire FastAPI process. This is acceptable for:
- Single-user localhost MVP
- Development/testing environment
- 7-day hackathon timeline

### Approach 2: Context Manager (Production-ready)

```python
# app/utils/gemini_context.py
import socket
import truststore
from contextlib import contextmanager

# Apply truststore once at module level
truststore.inject_into_ssl()

@contextmanager
def ipv4_context():
    """Temporarily force IPv4 for Gemini API calls"""
    original = socket.getaddrinfo
    
    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return original(host, port, socket.AF_INET, type, proto, flags)
    
    socket.getaddrinfo = ipv4_only
    try:
        yield
    finally:
        socket.getaddrinfo = original

# Usage in routes
from app.utils.gemini_context import ipv4_context
from google import genai

@router.post("/extract")
async def extract_document():
    with ipv4_context():
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(...)
    return response
```

---

## Security Notes

✅ **Safe:**
- API key from `.env` (not hardcoded)
- SSL verification enabled (via truststore)
- No keys in URLs or process args
- Socket patch scoped to process

⚠️ **Considerations:**
- Socket patch is process-wide (affects all connections in process)
- For production, consider per-request context manager
- truststore.inject_into_ssl() is global but safe

---

## Testing

### Verified Working:
```bash
cd tests
python test_truststore_ipv4.py
```

**Result:** ✅ 3.87s response, HTTP 200, correct output

---

## Alternative Solutions (Not Needed)

❌ **curl subprocess:** Security risk (keys in process args)  
❌ **Disable SSL verify:** Major security vulnerability  
❌ **Change Windows settings:** Affects entire system  
❌ **Only curl.exe:** Cannot integrate with FastAPI/Python code

---

## Migration Path

**For MVP (TASK-007):**
- Use Approach 1 (startup patches)
- Simple, works for localhost prototype

**For Production (future):**
- Use Approach 2 (context manager)
- Or resolve IPv6 at network level
- Or wait for google-genai SDK updates

---

**Status:** Ready for TASK-007 implementation  
**Updated:** requirements.txt includes `truststore`  
**Tested:** 2026-10-14, working on Windows with Python 3.13
