"""Analyze timeout source in Gemini call chain

This script traces the exact flow and identifies where timeout can occur:
1. Test script timeout (execute_pwsh)
2. google-genai SDK timeout
3. HTTP client timeout
4. Retry logic timeout
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

print("=" * 80)
print("TIMEOUT SOURCE ANALYSIS")
print("=" * 80)

# 1. Check google-genai SDK default timeout
print("\n[1] GOOGLE-GENAI SDK TIMEOUT")
try:
    from google import genai
    import inspect
    
    # Check Client class
    client_source = inspect.getsource(genai.Client)
    
    if 'timeout' in client_source.lower():
        print("    ✅ Client has timeout configuration")
        # Find default
        import re
        timeout_defaults = re.findall(r'timeout[=:\s]+(\d+)', client_source, re.IGNORECASE)
        if timeout_defaults:
            print(f"       Default timeout(s) found: {timeout_defaults}")
        else:
            print("       No explicit default found in source")
    else:
        print("    ⚠️  No timeout found in Client source")
    
    # Check if we can set timeout
    client_init_sig = inspect.signature(genai.Client.__init__)
    print(f"    Client.__init__ parameters: {list(client_init_sig.parameters.keys())}")
    
except Exception as e:
    print(f"    ❌ Could not analyze: {e}")

# 2. Check types.GenerateContentConfig
print("\n[2] GENERATE_CONTENT_CONFIG TIMEOUT")
try:
    from google.genai import types
    import inspect
    
    config_sig = inspect.signature(types.GenerateContentConfig)
    params = list(config_sig.parameters.keys())
    print(f"    GenerateContentConfig parameters: {params}")
    
    if 'timeout' in params:
        print("    ✅ timeout parameter available")
        default = config_sig.parameters['timeout'].default
        print(f"       Default: {default}")
    else:
        print("    ⚠️  No timeout parameter in GenerateContentConfig")
    
except Exception as e:
    print(f"    ❌ Could not analyze: {e}")

# 3. Check models.generate_content method
print("\n[3] MODELS.GENERATE_CONTENT METHOD")
try:
    from google import genai
    
    # Create dummy client to inspect method
    # (don't actually call API)
    client = genai.Client(api_key="dummy")
    
    import inspect
    generate_sig = inspect.signature(client.models.generate_content)
    params = list(generate_sig.parameters.keys())
    print(f"    generate_content parameters: {params}")
    
    if 'timeout' in params:
        print("    ✅ timeout parameter available")
        default = generate_sig.parameters['timeout'].default
        print(f"       Default: {default}")
    else:
        print("    ⚠️  No timeout parameter")
        
except Exception as e:
    print(f"    ❌ Could not analyze: {e}")

# 4. Analyze our code
print("\n[4] OUR GEMINI_ADAPTER TIMEOUT HANDLING")
try:
    from app.services.extraction.gemini_adapter import GeminiExtractor
    import inspect
    
    extract_source = inspect.getsource(GeminiExtractor.extract)
    
    # Check for timeout parameter in generate_content call
    if 'generate_content' in extract_source:
        print("    ✅ generate_content called in extract()")
        
        # Check if timeout is passed
        if 'timeout=' in extract_source:
            print("    ✅ timeout parameter is passed")
            import re
            timeout_val = re.search(r'timeout\s*=\s*(\d+)', extract_source)
            if timeout_val:
                print(f"       Value: {timeout_val.group(1)} seconds")
        else:
            print("    ⚠️  No timeout parameter passed - using SDK default")
    
    # Check for TimeoutError handling
    if 'TimeoutError' in extract_source or 'timeout' in extract_source.lower():
        print("    ✅ Timeout error handling exists")
    else:
        print("    ⚠️  No explicit timeout error handling")
        
except Exception as e:
    print(f"    ❌ Could not analyze: {e}")

# 5. Check for async vs sync
print("\n[5] ASYNC VS SYNC DETECTION")
try:
    from app.services.extraction.gemini_adapter import GeminiExtractor
    import inspect
    
    extract_source = inspect.getsource(GeminiExtractor.extract)
    
    if 'async def' in extract_source:
        print("    ℹ️  extract() is ASYNC")
    else:
        print("    ℹ️  extract() is SYNC")
    
    if 'await' in extract_source:
        print("    ⚠️  WARNING: await found in sync function - may cause blocking")
    
    # Check if generate_content is awaited
    if 'await client.models.generate_content' in extract_source:
        print("    ℹ️  generate_content is awaited (async call)")
    elif 'client.models.generate_content' in extract_source:
        print("    ℹ️  generate_content is called synchronously")
    
except Exception as e:
    print(f"    ❌ Could not analyze: {e}")

# 6. Check HTTP client underlying SDK
print("\n[6] UNDERLYING HTTP CLIENT")
try:
    import google.genai
    import pkg_resources
    
    # Get google-genai version
    try:
        version = pkg_resources.get_distribution("google-genai").version
        print(f"    google-genai version: {version}")
    except:
        print("    google-genai version: unknown")
    
    # Check what HTTP library it uses
    if hasattr(google.genai, '__file__'):
        import pathlib
        sdk_path = pathlib.Path(google.genai.__file__).parent
        print(f"    SDK location: {sdk_path}")
        
        # Check for httpx or requests
        try:
            import httpx
            print(f"    httpx available: {httpx.__version__}")
            print("       httpx default timeout: 5 seconds (connect/read)")
        except ImportError:
            pass
        
        try:
            import requests
            print(f"    requests available: {requests.__version__}")
            print("       requests default timeout: None (infinite)")
        except ImportError:
            pass
            
except Exception as e:
    print(f"    ❌ Could not analyze: {e}")

# Summary
print("\n" + "=" * 80)
print("TIMEOUT CHAIN SUMMARY")
print("=" * 80)
print("""
The 90-second timeout likely comes from:

1. ❌ NOT from execute_pwsh (that was 90000ms = 90s, just happened to match)
2. ❓ Possibly from google-genai SDK default (need to check SDK internals)
3. ❓ Possibly from underlying HTTP client (httpx/requests)
4. ⚠️  Our code does NOT set explicit timeout in generate_content()

CRITICAL FINDINGS:
- We don't pass timeout= parameter to generate_content()
- SDK will use its own default (unknown without SDK code inspection)
- If SDK uses httpx, default is 5s connect + 5s read
- If SDK uses requests without timeout, it's INFINITE (hangs forever)

The 90s timeout suggests:
- Either SDK has 90s default (unusual)
- Or multiple retries with 30s each (3 x 30s)
- Or the test script timeout killed it

RECOMMENDATION:
- Add explicit timeout=60 to generate_content() call
- Add proper timeout exception handling
- Add logging to see where it hangs
""")
print("=" * 80)
