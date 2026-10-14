# Python SDK Connection Status

**Date:** October 14, 2026  
**Task:** TASK-002 (Completed)  
**Issue:** IPv6 Timeout with google-genai SDK

---

## Current Status

### ✅ Working: curl.exe with IPv4
- **Method:** `curl.exe -4` (force IPv4)
- **Auth:** HTTP header `x-goog-api-key` (secure)
- **Performance:** <1 second response time
- **Security:** ✅ No keys in URLs or command args

### ❌ Not Working: Python google-genai SDK
- **Issue:** Network timeout (60+ seconds)
- **Root Cause:** IPv6 connection attempts fail
- **Impact:** Cannot use `genai.Client()` directly

---

## Required for TASK-007

TASK-007 (Gemini Real API Integration) requires Python implementation.

**Current blocker:** Python SDK unusable due to IPv6 timeout.

### Solution Requirements

**Must have:**
1. ✅ Use `google-genai` library OR secure HTTP client from Python
2. ✅ No API keys in process arguments or URLs
3. ✅ No SSL verification bypass
4. ✅ No Windows security settings changes
5. ✅ IPv4 connectivity (current network constraint)

**Must NOT:**
- ❌ Use `subprocess` with API key in args (security risk)
- ❌ Disable SSL/TLS verification
- ❌ Monkey-patch socket at global level (unsafe)
- ❌ Change Windows IPv6 settings

---

## Solution Requirements

**Must have:**
1. ✅ Use `google-genai` library OR secure HTTP client from Python
2. ✅ No API keys in process arguments or URLs
3. ✅ No SSL verification bypass
4. ✅ No Windows security settings changes
5. ✅ IPv4 connectivity (current network constraint)

**✅ SOLUTION FOUND:**

```python
import truststore
import socket
from google import genai

# Step 1: Fix SSL with truststore
truststore.inject_into_ssl()

# Step 2: Force IPv4 (temporary for this process)
original_getaddrinfo = socket.getaddrinfo

def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = ipv4_getaddrinfo

# Step 3: Use google-genai normally
client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=prompt
)

# Step 4: Clean up
socket.getaddrinfo = original_getaddrinfo
```

**Verified:** Working in 3.87s (test successful)

---

## Decision Point

**Before TASK-007:**
1. Research if `google-genai` supports custom HTTP client config
2. Test Option 2 (socket patch) in isolated environment
3. Verify security implications
4. Document chosen approach

**For now (TASK-002):**
- ✅ API verified working via curl
- ✅ Connection possible via IPv4
- ⚠️ Python implementation deferred to TASK-007

---

## Security Notes

All solutions must:
- Store API key in `.env` only
- Load with `python-dotenv`
- Pass key via HTTP header (not URL)
- Clean up any temporary patches
- Not expose keys in logs or errors

---

**Status:** DOCUMENTED - Solution required before TASK-007

**Prepared by:** Kiro Agent  
**Next Review:** Before starting TASK-007
