"""Test script to verify API key loading without exposing values."""
import os
import sys

# Load .env file
from pathlib import Path
env_path = Path(__file__).parent.parent / '.env'

if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Now test key manager
from app.services.extraction.gemini_key_manager import get_key_manager

km = get_key_manager()
status_list = km.get_status()
total_keys = km.get_total_key_count()
active_keys = km.get_active_key_count()

print("=" * 60)
print("API Key Manager Status")
print("=" * 60)
print(f"Total keys loaded: {total_keys}")
print(f"Active keys: {active_keys}")
print(f"Disabled keys: {total_keys - active_keys}")
print()
print("Key Details (no sensitive data):")
print("-" * 60)

for key_info in status_list:
    print(f"  {key_info['key_id']}:")
    print(f"    Source: {key_info['env_var']}")
    print(f"    Active: {key_info['is_active']}")
    print(f"    Failures: {key_info['failure_count']}")
    print(f"    Last used: {key_info['last_used'] or 'Never'}")
    print()

print("=" * 60)
print("Summary:")
print(f"  Keys found in .env: {total_keys}")
print(f"  Ready for use: {active_keys}")
if total_keys != 9:
    print(f"  WARNING: Expected 9 keys, found {total_keys}")
print("=" * 60)

