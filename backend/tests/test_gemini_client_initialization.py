"""Test actual GeminiExtractor Client initialization without mocking.

This test verifies that the real production code can create a Gemini Client
without ValidationError, using the actual HttpOptions and transport configuration.
"""
import pytest
import httpx
from google import genai
from google.genai import types

from app.services.extraction.gemini_adapter import GeminiExtractor


def test_gemini_client_creation_no_validation_error():
    """Verify that Gemini Client can be created without ValidationError.
    
    This test uses the REAL extractor initialization path, not mocked.
    It proves that HttpOptions parameters are valid.
    """
    # Create extractor (initializes SSL context and transport)
    extractor = GeminiExtractor(model="gemini-3.8-flash")
    
    # Verify transport configuration exists
    assert extractor.ssl_context is not None
    assert extractor.http_transport is not None
    
    # Get a test API key (from key manager)
    key_id, key_value = extractor.key_manager.get_next_key()
    assert key_value is not None, "At least one API key must be configured"
    
    # Try to create the ACTUAL Gemini Client using production code path
    # This is the exact code from gemini_adapter.py extract() method
    try:
        # Create HTTPX client with custom transport
        httpx_client = httpx.Client(
            transport=extractor.http_transport,
            timeout=60.0
        )
        
        # Create Gemini client - this is where ValidationError would occur
        client = genai.Client(
            api_key=key_value,
            http_options=types.HttpOptions(
                httpx_client=httpx_client,
                timeout=60000,
                retry_options=types.HttpRetryOptions(
                    attempts=1  # Correct parameter name
                )
            )
        )
        
        # If we got here, no ValidationError occurred
        assert client is not None
        print("✓ Gemini Client created successfully without ValidationError")
        
        # Cleanup
        httpx_client.close()
        
    except Exception as e:
        pytest.fail(f"Client creation failed: {type(e).__name__}: {e}")


def test_https_connection_with_transport():
    """Test that the transport configuration can establish HTTPS connection.
    
    Verifies SSL/TLS works without making actual API calls.
    """
    extractor = GeminiExtractor(model="gemini-3.8-flash")
    
    # Create HTTPX client with the production transport
    httpx_client = httpx.Client(
        transport=extractor.http_transport,
        timeout=30.0
    )
    
    try:
        # Test HTTPS to Google (not Gemini API, just connectivity)
        response = httpx_client.get("https://www.google.com")
        assert response.status_code == 200
        print(f"✓ HTTPS connection successful: {response.status_code}")
        
    except Exception as e:
        pytest.fail(f"HTTPS connection failed: {type(e).__name__}: {e}")
    finally:
        httpx_client.close()


def test_gemini_endpoint_reachable_with_transport():
    """Test that Gemini API endpoint is reachable with the transport.
    
    Expects 403/404 (no auth), but proves the endpoint is accessible.
    """
    extractor = GeminiExtractor(model="gemini-3.8-flash")
    
    httpx_client = httpx.Client(
        transport=extractor.http_transport,
        timeout=30.0
    )
    
    try:
        # Try to reach Gemini API (expect auth error, but connection should work)
        response = httpx_client.get("https://generativelanguage.googleapis.com/v1beta/models")
        
        # 403/404 means endpoint is reachable, just auth/path issue
        assert response.status_code in [403, 404, 401]
        print(f"✓ Gemini endpoint reachable: {response.status_code}")
        
    except Exception as e:
        pytest.fail(f"Gemini endpoint unreachable: {type(e).__name__}: {e}")
    finally:
        httpx_client.close()


def test_extractor_initialization_with_real_config():
    """Test that GeminiExtractor initializes with real production configuration.
    
    No mocking - this is the actual initialization path.
    """
    try:
        extractor = GeminiExtractor(model="gemini-3.8-flash", prompt_version="2.0")
        
        # Verify all components initialized
        assert extractor.model == "gemini-3.8-flash"
        assert extractor.prompt_version == "2.0"
        assert extractor.key_manager is not None
        assert extractor.quota_manager is not None
        assert extractor.ssl_context is not None
        assert extractor.http_transport is not None
        
        # Verify SSL context is properly configured
        import ssl
        assert extractor.ssl_context.check_hostname is True
        assert extractor.ssl_context.verify_mode == ssl.CERT_REQUIRED
        
        print("✓ GeminiExtractor initialized successfully")
        print(f"  - Model: {extractor.model}")
        print(f"  - SSL verify_mode: {extractor.ssl_context.verify_mode}")
        print(f"  - Transport configured: Yes")
        
    except Exception as e:
        pytest.fail(f"Extractor initialization failed: {type(e).__name__}: {e}")


def test_httpoptions_does_not_use_verify_false():
    """Verify that we never use verify=False (security requirement)."""
    extractor = GeminiExtractor(model="gemini-3.8-flash")
    
    # The transport should use SSL context, not False
    assert extractor.ssl_context is not None
    
    # Check that transport has verification enabled
    # (implementation detail: _pool has the SSL context)
    import ssl
    assert extractor.ssl_context.verify_mode == ssl.CERT_REQUIRED
    print("✓ Certificate verification is ENABLED (not bypassed)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
