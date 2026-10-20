"""Check if gemini-1.5-flash is available and verify Free Tier quota."""
import os
import sys
from pathlib import Path

# Load .env
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Get first API key
api_key = os.getenv('GEMINI_API_KEY', '').strip()

if not api_key:
    print("ERROR: No GEMINI_API_KEY found in .env")
    sys.exit(1)

print("=" * 70)
print("Checking Gemini Model Availability")
print("=" * 70)
print(f"Model: {os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')}")
print(f"API Key: {api_key[:10]}...{api_key[-4:]} (first key)")
print()

try:
    import google.generativeai as genai
    
    # Configure with first key
    client = genai.Client(api_key=api_key)
    
    print("Listing available models...")
    print("-" * 70)
    
    models_info = []
    for model in client.models.list():
        # Check if model supports generateContent
        supports_generate = any('generateContent' in m for m in (model.supported_generation_methods or []))
        
        if supports_generate:
            models_info.append({
                'name': model.name,
                'display_name': model.display_name,
                'description': model.description[:80] + '...' if len(model.description) > 80 else model.description,
                'input_token_limit': model.input_token_limit,
                'output_token_limit': model.output_token_limit
            })
    
    # Find gemini-1.5-flash variants
    flash_models = [m for m in models_info if '1.5' in m['name'] and 'flash' in m['name'].lower()]
    
    print(f"\nFound {len(models_info)} models that support generateContent")
    print(f"Found {len(flash_models)} Gemini 1.5 Flash variants")
    print()
    
    if flash_models:
        print("=" * 70)
        print("Gemini 1.5 Flash Models:")
        print("=" * 70)
        for m in flash_models:
            print(f"\nModel: {m['name']}")
            print(f"  Display Name: {m['display_name']}")
            print(f"  Description: {m['description']}")
            print(f"  Input Tokens: {m['input_token_limit']:,}")
            print(f"  Output Tokens: {m['output_token_limit']:,}")
    else:
        print("⚠️  WARNING: No Gemini 1.5 Flash models found!")
        print("\nShowing first 5 available models:")
        print("-" * 70)
        for m in models_info[:5]:
            print(f"  - {m['name']}")
    
    print("\n" + "=" * 70)
    print("Quota Information")
    print("=" * 70)
    print("NOTE: Quota limits are NOT returned by API.")
    print("      Free Tier limits vary by model and region.")
    print()
    print("Expected limits for gemini-1.5-flash (Free Tier):")
    print("  - Requests Per Minute (RPM): 15")
    print("  - Requests Per Day (RPD): 1500")
    print("  - Tokens Per Minute (TPM): 1,000,000")
    print()
    print("⚠️  IMPORTANT: Verify actual limits in Google AI Studio:")
    print("   https://ai.google.dev/")
    print("=" * 70)
    
    # Check if target model exists
    target_model = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
    model_found = any(target_model in m['name'] for m in models_info)
    
    if model_found:
        print(f"\n✅ Model '{target_model}' is AVAILABLE")
    else:
        print(f"\n❌ Model '{target_model}' NOT FOUND")
        print(f"   Consider using: {flash_models[0]['name'] if flash_models else 'gemini-1.5-flash-latest'}")
    
    print("=" * 70)

except ImportError:
    print("❌ ERROR: google-generativeai not installed")
    print("   Run: pip install google-generativeai")
    sys.exit(1)

except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")
    sys.exit(1)
