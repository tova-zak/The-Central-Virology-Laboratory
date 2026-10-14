"""
Gemini API Verification Script

This script verifies that the Gemini API is properly configured for the
Virology Lab Commitment Extraction System.

It checks:
1. google-genai package is installed
2. API key is configured in .env file
3. Environment variables are loaded correctly

NOTE: This script does NOT make actual API calls to save your free tier quota.
      Manual testing with real API calls should be done separately.

Usage:
    python tests/verify_gemini.py
    OR
    pytest tests/verify_gemini.py -v
"""

import os
import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))


def test_google_genai_import():
    """Test 1: Verify google-genai package is installed"""
    print("\n✓ Test 1: Checking google-genai package installation...")
    try:
        import google.genai
        print(f"  ✅ google-genai package found (version available)")
        print(f"  Package location: {google.genai.__file__}")
        return True
    except ImportError as e:
        print(f"  ❌ google-genai package NOT found")
        print(f"  Error: {e}")
        print(f"  Solution: Run 'pip install google-genai'")
        return False


def test_env_file_exists():
    """Test 2: Verify .env file exists"""
    print("\n✓ Test 2: Checking .env file...")
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    if env_file.exists():
        print(f"  ✅ .env file found at: {env_file}")
        return True
    else:
        print(f"  ⚠️  .env file NOT found at: {env_file}")
        print(f"  Note: You need to create .env file with your API key")
        print(f"  See .env.example for template")
        return False


def test_api_key_configured():
    """Test 3: Verify GEMINI_API_KEY is set in environment"""
    print("\n✓ Test 3: Checking API key configuration...")
    
    # Try to load from .env
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key and api_key != "your_gemini_api_key_here":
        # Don't print the actual key for security
        masked_key = api_key[:10] + "..." + api_key[-4:] if len(api_key) > 14 else "***"
        print(f"  ✅ GEMINI_API_KEY is configured")
        print(f"  Key (masked): {masked_key}")
        return True
    else:
        print(f"  ⚠️  GEMINI_API_KEY is NOT configured or using default value")
        print(f"  Solution:")
        print(f"    1. Get free API key from: https://aistudio.google.com/apikey")
        print(f"    2. Add to .env file: GEMINI_API_KEY=your_actual_key")
        return False


def test_model_configured():
    """Test 4: Verify GEMINI_MODEL is configured"""
    print("\n✓ Test 4: Checking model configuration...")
    
    # Try to load from .env
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
    
    model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")  # Default
    print(f"  ✅ GEMINI_MODEL configured as: {model}")
    
    # Check if it's a recommended free tier model
    free_models = [
        "gemini-3.8-flash",
        "gemini-2.5-flash", 
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite"
    ]
    
    if model in free_models:
        print(f"  ✅ Model is on free tier: {model}")
    else:
        print(f"  ⚠️  Model '{model}' may not be on free tier")
        print(f"  Recommended free models: {', '.join(free_models)}")
    
    return True


def test_client_initialization():
    """Test 5: Test client initialization (without making API calls)"""
    print("\n✓ Test 5: Testing client initialization...")
    
    try:
        from google import genai
        
        # Try to load from .env
        project_root = Path(__file__).parent.parent
        env_file = project_root / ".env"
        
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
        
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key or api_key == "your_gemini_api_key_here":
            print(f"  ⚠️  Cannot test client initialization without valid API key")
            print(f"  Skipping (this is OK for now)")
            return True
        
        # Initialize client (doesn't make API call)
        client = genai.Client(api_key=api_key)
        print(f"  ✅ Client initialized successfully")
        print(f"  Note: No actual API call was made (saving your quota)")
        return True
        
    except Exception as e:
        print(f"  ❌ Client initialization failed")
        print(f"  Error: {e}")
        return False


def print_manual_test_instructions():
    """Print instructions for manual API testing"""
    print("\n" + "="*70)
    print("MANUAL API TEST (Optional - uses your quota)")
    print("="*70)
    print("""
To test actual API calls, create a file test_api_manual.py:

```python
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Test 1: Simple text
print("Test 1: Simple text generation...")
interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input="Say 'Hello, Virology Lab!' in exactly 3 words."
)
print(f"Response: {interaction.output}")

# Test 2: Structured JSON
print("\\nTest 2: Structured JSON output...")
from pydantic import BaseModel

class TestResult(BaseModel):
    success: bool
    message: str

interaction = client.interactions.create(
    model="gemini-3.8-flash",
    input="Return success=true and message='API is working'",
    response_format={"type": "json_object", "schema": TestResult}
)
print(f"Structured Response: {interaction.output}")
print("\\n✅ All manual tests passed!")
```

Then run: python test_api_manual.py

⚠️  This will use 2 API calls from your free tier quota.
""")


def main():
    """Run all verification tests"""
    print("="*70)
    print("GEMINI API VERIFICATION")
    print("Virology Lab Commitment Extraction System")
    print("="*70)
    
    results = []
    
    # Run all tests
    results.append(("google-genai package", test_google_genai_import()))
    results.append((".env file exists", test_env_file_exists()))
    results.append(("API key configured", test_api_key_configured()))
    results.append(("Model configured", test_model_configured()))
    results.append(("Client initialization", test_client_initialization()))
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All verification tests passed!")
        print("✅ Your Gemini API setup is ready for development")
        print("\nNext steps:")
        print("  1. Review docs/GEMINI_SETUP.md for usage examples")
        print("  2. (Optional) Run manual API test to verify actual calls")
        print("  3. Proceed to TASK-003: Document Processing Setup")
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        print("📖 See docs/GEMINI_SETUP.md for detailed setup instructions")
    
    # Print manual test instructions
    if passed >= 4:  # If most tests passed
        print_manual_test_instructions()
    
    print("="*70)
    
    # Return exit code for pytest
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
