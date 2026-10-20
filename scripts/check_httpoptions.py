#!/usr/bin/env python3
"""Check HttpOptions supported fields in google-genai."""

from google.genai import types
import inspect

print("google-genai HttpOptions inspection")
print("="*60)

# Get HttpOptions
http_options = types.HttpOptions

print(f"\nHttpOptions class: {http_options}")
print(f"\nType: {type(http_options)}")

# Try to get model fields (Pydantic)
if hasattr(http_options, 'model_fields'):
    print("\n✓ HttpOptions.model_fields:")
    for field_name, field_info in http_options.model_fields.items():
        print(f"  - {field_name}: {field_info.annotation}")
elif hasattr(http_options, '__fields__'):
    print("\n✓ HttpOptions.__fields__:")
    for field_name, field_info in http_options.__fields__.items():
        print(f"  - {field_name}: {field_info.type_}")
else:
    print("\n⚠ No Pydantic fields found, checking __init__ signature:")
    sig = inspect.signature(http_options.__init__)
    for param_name, param in sig.parameters.items():
        if param_name != 'self':
            print(f"  - {param_name}: {param.annotation}")

# Try to instantiate with different options
print("\n" + "="*60)
print("Testing HttpOptions instantiation")
print("="*60)

# Test 1: Empty
try:
    opts = types.HttpOptions()
    print("✓ Empty HttpOptions: SUCCESS")
except Exception as e:
    print(f"✗ Empty HttpOptions: {e}")

# Test 2: timeout only
try:
    opts = types.HttpOptions(timeout=60000)
    print("✓ HttpOptions(timeout=60000): SUCCESS")
except Exception as e:
    print(f"✗ HttpOptions(timeout=60000): {e}")

# Test 3: client (not supported according to error)
try:
    import httpx
    client = httpx.Client()
    opts = types.HttpOptions(client=client)
    print("✓ HttpOptions(client=...): SUCCESS")
    client.close()
except Exception as e:
    print(f"✗ HttpOptions(client=...): {type(e).__name__}: {e}")

# Test 4: client_args
try:
    opts = types.HttpOptions(client_args={'timeout': 60.0})
    print("✓ HttpOptions(client_args=...): SUCCESS")
except Exception as e:
    print(f"✗ HttpOptions(client_args=...): {type(e).__name__}: {e}")

# Test 5: httpx_client
try:
    import httpx
    client = httpx.Client()
    opts = types.HttpOptions(httpx_client=client)
    print("✓ HttpOptions(httpx_client=...): SUCCESS")
    client.close()
except Exception as e:
    print(f"✗ HttpOptions(httpx_client=...): {type(e).__name__}: {e}")

print("\n" + "="*60)
