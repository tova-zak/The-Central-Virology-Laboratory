#!/usr/bin/env python3
"""
Test script to verify HTTP transport configuration works with Google APIs.
Tests HTTPS connectivity without making actual API calls.
"""

import sys
import ssl
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

import truststore
import httpx


def test_basic_https_connectivity():
    """Test basic HTTPS connectivity to Google domain."""
    print("="*60)
    print("Testing Basic HTTPS Connectivity to Google")
    print("="*60)
    
    try:
        # Create SSL context with truststore
        print("\n1. Creating SSL context with truststore...")
        ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        print("   ✓ SSL context created")
        
        # Create HTTP transport with IPv4 only
        print("\n2. Creating HTTP transport (IPv4 only)...")
        transport = httpx.HTTPTransport(
            verify=ssl_context,
            local_address="0.0.0.0"
        )
        print("   ✓ Transport created")
        
        # Create HTTPX client
        print("\n3. Creating HTTPX client...")
        client = httpx.Client(
            transport=transport,
            timeout=30.0
        )
        print("   ✓ Client created")
        
        # Test ction to Google (not Gemini API)
        print("\n4. Testing HTTPS connection to www.google.com...")
        response = client.get("https://www.google.com")
        print(f"   ✓ Response status: {response.status_code}")
        print(f"   ✓ Response size: {len(response.content)} bytes")
        
        # Test connection to Google API base (no auth needed)
        print("\n5. Testing HTTPS connection to googleapis.com...")
        response = client.get("https://www.googleapis.com")
        print(f"   ✓ Response status: {response.status_code}")
        
        print("\n" + "="*60)
        print("✓ SUCCESS: HTTPS connectivity is working!")
        print("="*60)
        print("\nTransport Configuration:")
        print("  - SSL Context: truststore.SSLContext")
        print("  - Local Address: 0.0.0.0 (IPv4 only)")
        print("  - Certificate Verification: ENABLED")
        print("  - Timeout: 30 seconds")
        
        return True
        
    except Exception as e:
        print(f"\n✗ FAILED: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'client' in locals():
            client.close()


def test_gemini_endpoint_reachable():
    """Test if Gemini API endpoint is reachable (expect 404 without auth)."""
    print("\n" + "="*60)
    print("Testing Gemini API Endpoint Reachability")
    print("="*60)
    
    try:
        # Create configured client
        ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        transport = httpx.HTTPTransport(
            verify=ssl_context,
            local_address="0.0.0.0"
        )
        client = httpx.Client(transport=transport, timeout=30.0)
        
        # Try to reach Gemini API base (expect 404 without proper auth/path)
        print("\nTesting: https://generativelanguage.googleapis.com/v1beta/models")
        response = client.get("https://generativelanguage.googleapis.com/v1beta/models")
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 404:
            print("✓ Endpoint is reachable (404 expected without API key)")
            return True
        elif response.status_code == 401 or response.status_code == 403:
            print("✓ Endpoint is reachable (auth error expected)")
            return True
        else:
            print(f"⚠ Unexpected status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return True  # Still reachable
        
    except Exception as e:
        print(f"✗ FAILED to reach endpoint: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'client' in locals():
            client.close()


def main():
    """Run all transport tests."""
    print("HTTP Transport Configuration Test")
    print("="*60)
    print("This test verifies that the transport configuration")
    print("(IPv4 + truststore SSL) works for HTTPS connections.")
    print("="*60)
    
    # Test 1: Basic HTTPS
    test1_passed = test_basic_https_connectivity()
    
    # Test 2: Gemini endpoint
    test2_passed = test_gemini_endpoint_reachable()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Basic HTTPS connectivity: {'✓ PASS' if test1_passed else '✗ FAIL'}")
    print(f"Gemini endpoint reachable: {'✓ PASS' if test2_passed else '✗ FAIL'}")
    
    if test1_passed and test2_passed:
        print("\n✓ All transport tests PASSED")
        print("GeminiExtractor is ready for API calls with this configuration.")
        return 0
    else:
        print("\n✗ Some tests FAILED")
        print("Transport configuration needs adjustment.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
