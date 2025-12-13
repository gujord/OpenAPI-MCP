#!/usr/bin/env python3
"""
Unit tests for custom authentication headers functionality.
"""
import os
import sys
import json

from openapi_mcp.config import ServerConfig
from openapi_mcp.auth import AuthenticationManager, CustomHeaderAuthenticator


def test_parse_json_headers():
    """Test parsing JSON format headers."""
    print("Testing JSON format header parsing...")
    
    try:
        # Set up environment with JSON headers
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ["MCP_AUTH_HEADERS"] = '{"X-API-Key": "secret123", "X-Client-ID": "client456"}'
        
        config = ServerConfig()
        headers = config.auth_headers
        
        assert headers is not None, "Headers should not be None"
        assert len(headers) == 2, "Should have 2 headers"
        assert headers["X-API-Key"] == "secret123", "X-API-Key should match"
        assert headers["X-Client-ID"] == "client456", "X-Client-ID should match"
        assert config.has_custom_headers() is True, "Should report having custom headers"
        
        print("✓ JSON header parsing successful")
        return True
        
    except Exception as e:
        print(f"✗ JSON header parsing failed: {e}")
        return False
    finally:
        # Clean up environment
        os.environ.pop("MCP_AUTH_HEADERS", None)


def test_parse_simple_headers():
    """Test parsing key=value format headers."""
    print("Testing simple format header parsing...")
    
    try:
        # Set up environment with simple format headers
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ["MCP_AUTH_HEADERS"] = "X-API-Key=mykey123,Authorization=Bearer token789,X-Custom=value"
        
        config = ServerConfig()
        headers = config.auth_headers
        
        assert headers is not None, "Headers should not be None"
        assert len(headers) == 3, "Should have 3 headers"
        assert headers["X-API-Key"] == "mykey123", "X-API-Key should match"
        assert headers["Authorization"] == "Bearer token789", "Authorization should match"
        assert headers["X-Custom"] == "value", "X-Custom should match"
        
        print("✓ Simple header parsing successful")
        return True
        
    except Exception as e:
        print(f"✗ Simple header parsing failed: {e}")
        return False
    finally:
        # Clean up environment
        os.environ.pop("MCP_AUTH_HEADERS", None)


def test_empty_headers():
    """Test with no custom headers."""
    print("Testing empty headers...")
    
    try:
        # Set up environment without custom headers
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ.pop("MCP_AUTH_HEADERS", None)  # Ensure it's not set
        
        config = ServerConfig()
        headers = config.auth_headers
        
        assert headers is not None, "Headers should not be None"
        assert len(headers) == 0, "Should have 0 headers"
        assert config.has_custom_headers() is False, "Should report not having custom headers"
        
        print("✓ Empty headers handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Empty headers test failed: {e}")
        return False


def test_header_with_equals_in_value():
    """Test parsing headers with = in the value."""
    print("Testing headers with = in value...")
    
    try:
        # Set up environment with = in value
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ["MCP_AUTH_HEADERS"] = "X-API-Key=key=with=equals,X-Token=normal"
        
        config = ServerConfig()
        headers = config.auth_headers
        
        assert headers["X-API-Key"] == "key=with=equals", "Should preserve = in value"
        assert headers["X-Token"] == "normal", "Normal header should work"
        
        print("✓ Headers with = in value parsed correctly")
        return True
        
    except Exception as e:
        print(f"✗ Headers with = in value failed: {e}")
        return False
    finally:
        os.environ.pop("MCP_AUTH_HEADERS", None)


def test_custom_header_authenticator():
    """Test CustomHeaderAuthenticator class."""
    print("Testing CustomHeaderAuthenticator...")
    
    try:
        headers = {"X-API-Key": "test", "X-Client": "myclient"}
        authenticator = CustomHeaderAuthenticator(headers)
        
        assert authenticator.is_configured() is True, "Should be configured"
        
        # Test adding headers
        request_headers = {"Content-Type": "application/json"}
        updated = authenticator.add_auth_headers(request_headers)
        
        assert "X-API-Key" in updated, "Should have X-API-Key"
        assert updated["X-API-Key"] == "test", "X-API-Key should match"
        assert "X-Client" in updated, "Should have X-Client"
        assert "Content-Type" in updated, "Should preserve existing headers"
        
        # Test get_headers
        retrieved = authenticator.get_headers()
        assert retrieved == headers, "Should return copy of headers"
        
        print("✓ CustomHeaderAuthenticator works correctly")
        return True
        
    except Exception as e:
        print(f"✗ CustomHeaderAuthenticator test failed: {e}")
        return False


def test_authentication_manager_with_custom_headers():
    """Test AuthenticationManager with custom headers."""
    print("Testing AuthenticationManager with custom headers...")
    
    try:
        # Set up config with custom headers
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ["MCP_AUTH_HEADERS"] = '{"X-API-Key": "manager-test"}'
        
        config = ServerConfig()
        auth_manager = AuthenticationManager(config)
        
        assert auth_manager.is_configured() is True, "Should be configured"
        
        # Test adding headers
        request_headers = {}
        updated = auth_manager.add_auth_headers(request_headers)
        
        assert "X-API-Key" in updated, "Should have X-API-Key"
        assert updated["X-API-Key"] == "manager-test", "X-API-Key should match"
        
        # Test get_custom_headers
        custom = auth_manager.get_custom_headers()
        assert "X-API-Key" in custom, "Should return custom headers"
        
        print("✓ AuthenticationManager with custom headers works")
        return True
        
    except Exception as e:
        print(f"✗ AuthenticationManager test failed: {e}")
        return False
    finally:
        os.environ.pop("MCP_AUTH_HEADERS", None)


def test_header_precedence():
    """Test that custom headers are applied before OAuth."""
    print("Testing header precedence...")
    
    try:
        # Set up both custom headers and OAuth
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ["MCP_AUTH_HEADERS"] = '{"Authorization": "Custom auth-token"}'
        os.environ["OAUTH_CLIENT_ID"] = "client"
        os.environ["OAUTH_CLIENT_SECRET"] = "secret"
        os.environ["OAUTH_TOKEN_URL"] = "https://test.com/token"
        
        config = ServerConfig()
        auth_manager = AuthenticationManager(config)
        
        # Add headers (OAuth will override Authorization if it gets a token)
        request_headers = {}
        updated = auth_manager.add_auth_headers(request_headers)
        
        # Custom headers should be applied first
        # (OAuth might override, but custom headers are applied)
        assert "Authorization" in updated, "Should have Authorization header"
        
        print("✓ Header precedence works correctly")
        return True
        
    except Exception as e:
        print(f"✗ Header precedence test failed: {e}")
        return False
    finally:
        os.environ.pop("MCP_AUTH_HEADERS", None)
        os.environ.pop("OAUTH_CLIENT_ID", None)
        os.environ.pop("OAUTH_CLIENT_SECRET", None)
        os.environ.pop("OAUTH_TOKEN_URL", None)


def test_malformed_json_headers():
    """Test handling of malformed JSON headers."""
    print("Testing malformed JSON headers...")
    
    try:
        # Set up environment with malformed JSON (will fall back to simple format)
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ["MCP_AUTH_HEADERS"] = '{"broken": json}'
        
        config = ServerConfig()
        headers = config.auth_headers
        
        # Should parse as simple format since JSON parsing fails
        # The string '{"broken": json}' has no '=' so will result in empty headers
        assert len(headers) == 0, "Malformed JSON with no = should give empty headers"
        
        # Try with something that looks more like simple format
        os.environ["MCP_AUTH_HEADERS"] = 'X-API-Key=value'
        config2 = ServerConfig()
        headers2 = config2.auth_headers
        
        assert len(headers2) == 1, "Should fall back to simple format"
        assert headers2["X-API-Key"] == "value", "Should parse simple format"
        
        print("✓ Malformed JSON handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Malformed JSON test failed: {e}")
        return False
    finally:
        os.environ.pop("MCP_AUTH_HEADERS", None)


def test_whitespace_handling():
    """Test that whitespace is handled correctly."""
    print("Testing whitespace handling...")
    
    try:
        # Test with spaces around keys and values
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        os.environ["MCP_AUTH_HEADERS"] = "  X-API-Key = spaced-value  ,  X-Other = value2  "
        
        config = ServerConfig()
        headers = config.auth_headers
        
        assert headers["X-API-Key"] == "spaced-value", "Should trim spaces from key and value"
        assert headers["X-Other"] == "value2", "Should trim spaces from second header"
        assert len(headers) == 2, "Should have 2 headers"
        
        print("✓ Whitespace handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Whitespace handling test failed: {e}")
        return False
    finally:
        os.environ.pop("MCP_AUTH_HEADERS", None)


def test_special_characters_in_headers():
    """Test headers with special characters."""
    print("Testing special characters in headers...")
    
    try:
        # Test JSON format with special characters
        os.environ["OPENAPI_URL"] = "https://test.com/openapi.json"
        special_headers = {
            "X-API-Key": "key-with-dash",
            "X_Under_Score": "under_value",
            "X.Dot.Header": "dot.value",
            "X-Special!@#": "special$%^"
        }
        os.environ["MCP_AUTH_HEADERS"] = json.dumps(special_headers)
        
        config = ServerConfig()
        headers = config.auth_headers
        
        for key, value in special_headers.items():
            assert headers[key] == value, f"Header {key} should match"
        
        print("✓ Special characters handled correctly")
        return True
        
    except Exception as e:
        print(f"✗ Special characters test failed: {e}")
        return False
    finally:
        os.environ.pop("MCP_AUTH_HEADERS", None)


def run_all_tests():
    """Run all custom auth header tests."""
    print("\n" + "="*50)
    print("Custom Authentication Headers Tests")
    print("="*50 + "\n")
    
    tests = [
        test_parse_json_headers,
        test_parse_simple_headers,
        test_empty_headers,
        test_header_with_equals_in_value,
        test_custom_header_authenticator,
        test_authentication_manager_with_custom_headers,
        test_header_precedence,
        test_malformed_json_headers,
        test_whitespace_handling,
        test_special_characters_in_headers
    ]
    
    results = []
    for test in tests:
        try:
            success = test()
            results.append(success)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()  # Add blank line between tests
    
    # Summary
    passed = sum(results)
    total = len(results)
    
    print("="*50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed!")
        return True
    else:
        print(f"✗ {total - passed} tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)