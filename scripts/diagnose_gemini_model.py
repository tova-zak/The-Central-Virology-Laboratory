#!/usr/bin/env python3
"""
Minimal diagnostic script to test Gemini Activity and model availability.
Tests one API key with a trivial request to identify the root cause of timeouts.
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment from project root .env
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)
print(f"Loading .env from: {env_path}")
print(f".env exists: {env_path.exists()}")

def test_api_key(api_key: str, key_name: str) -> dict:
    """Test a single API key with minimal request."""
    print(f"\n{'='*60}")
    print(f"Testing {key_name}")
    print(f"{'='*60}")
    
    try:
        # Create client with timeout
        print("Creating Gemini client...")
        client = genai.Client(
            api_key=api_key,
            http_options={'timeout': 30}  # 30 second timeout
        )
        
        print("✓ Client created successfully")
        
        # List available models
        print("\nListing available models...")
        models_response = client.models.list()
        available_models = [m.name for m in models_response.models]
        
        print(f"✓ Found {len(available_models)} models")
        
        if available_models:
            print("Available models:")
            for model in available_models[:10]:
                print(f"  - {model}")
        
        # Check if our model exists
        target_model = "gemini-3.8-flash"
        full_model_name = f"models/{target_model}"
        
        if full_model_name in available_models or target_model in [m.split('/')[-1] for m in available_models]:
            print(f"✓ Model {target_model} is available")
        else:
            print(f"✗ Model {target_model} NOT FOUND")
            return {
                "success": False,
                "error": f"Model {target_model} not available",
                "available_models": available_models
            }
        
        # Try minimal generation
        print(f"\nTesting minimal generation with {target_model}...")
        
        response = client.models.generate_content(
            model=target_model,
            contents="Say 'OK' if you receive this.",
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=10
            )
        )
        
        print(f"✓ Generation successful")
        print(f"Response: {response.text[:100]}")
        
        return {
            "success": True,
            "response": response.text,
            "available_models": available_models
        }
        
    except Exception as e:
        print(f"✗ Error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        }


def main():
    """Run diagnostics on first API key."""
    print("Gemini API Model Diagnostic")
    print("="*60)
    
    # Get first API key (using correct env var name)
    api_key = os.getenv("GEMINI_API_1")
    if not api_key:
        print("✗ GEMINI_API_1 not found in environment")
        return 1
    
    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    
    # Test the key
    result = test_api_key(api_key, "GEMINI_API_1")
    
    # Summary
    print(f"\n{'='*60}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'='*60}")
    
    if result["success"]:
        print("✓ API key is valid and working")
        print("✓ Model gemini-3.8-flash is accessible")
        print("✓ Generation completed successfully")
        print("\nROOT CAUSE: Not an API/model availability issue")
        print("NEXT STEP: Check SDK version, request parameters, or quota limits")
        return 0
    else:
        print("✗ Test failed")
        print(f"Error: {result.get('error', 'Unknown error')}")
        
        if "available_models" in result:
            print(f"\nAvailable models to try:")
            for model in result["available_models"][:10]:
                print(f"  - {model}")
        
        print("\nROOT CAUSE: API connectivity or model availability issue")
        print("NEXT STEP: Switch to working model or fix API key configuration")
        return 1


if __name__ == "__main__":
    sys.exit(main())
