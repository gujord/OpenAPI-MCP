#!/usr/bin/env python3
"""
Integration tests for local file loading and custom auth headers.
"""
import os
import sys
import asyncio

from openapi_mcp.config import ServerConfig
from openapi_mcp.auth import AuthenticationManager
from openapi_mcp.openapi_loader import OpenAPILoader
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


async def test_local_spec_with_custom_auth():
    """Test loading local spec and using custom auth headers."""
    print("Testing local spec with custom auth headers...")
    
    try:
        # Set up environment
        os.environ["OPENAPI_URL"] = "./test/fixtures/petstore.json"
        os.environ["SERVER_NAME"] = "test_petstore"
        os.environ["MCP_AUTH_HEADERS"] = '{"X-API-Key": "test-key-123", "X-Client-ID": "test-client"}'
        
        config = ServerConfig()
        
        # Verify local spec loading
        assert not config.openapi_url.startswith("http"), "Should be local file"
        
        # Verify custom headers
        assert config.has_custom_headers(), "Should have custom headers"
        assert config.auth_headers["X-API-Key"] == "test-key-123", "API key should match"
        
        # Create and initialize server
        server = FastMCPOpenAPIServer(config)
        await server.initialize()
        
        # Verify spec was loaded
        assert server.openapi_spec is not None, "Spec should be loaded"
        assert server.openapi_spec["info"]["title"] == "Test Petstore API", "Title should match"
        
        # Verify operations were registered
        assert len(server.operations) > 0, "Should have operations"
        operation_ids = [op.operation_id for op in server.operations]
        assert "listPets" in operation_ids, "Should have listPets operation"
        
        # Verify auth manager has custom headers
        auth_headers = server.authenticator.get_custom_headers()
        assert "X-API-Key" in auth_headers, "Should have API key in auth"
        
        print("✓ Local spec with custom auth successful")
        return True
        
    except Exception as e:
        print(f"✗ Local spec with custom auth failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up environment
        os.environ.pop("MCP_AUTH_HEADERS", None)


async def test_weather_api_with_local_spec():
    """Test weather API using local OpenAPI spec."""
    print("Testing weather API with local spec...")
    
    try:
        # Set up environment for local weather spec
        os.environ["OPENAPI_URL"] = "./test/fixtures/weather.yaml"
        os.environ["SERVER_NAME"] = "test_weather"
        os.environ.pop("MCP_AUTH_HEADERS", None)  # No auth for this test
        
        config = ServerConfig()
        server = FastMCPOpenAPIServer(config)
        await server.initialize()
        
        # Verify YAML spec was loaded
        assert server.openapi_spec["info"]["title"] == "Test Weather API", "Title should match"
        assert server.openapi_spec["info"]["version"] == "1.0.0", "Version should match"
        
        # Verify weather operations
        operation_ids = [op.operation_id for op in server.operations]
        assert "getForecast" in operation_ids, "Should have getForecast"
        assert "getCurrentWeather" in operation_ids, "Should have getCurrentWeather"
        
        # Find getForecast operation
        forecast_op = next((op for op in server.operations if op.operation_id == "getForecast"), None)
        assert forecast_op is not None, "Should find getForecast operation"
        
        # Verify parameters
        param_names = [p.get("name") for p in forecast_op.parameters]
        assert "lat" in param_names, "Should have lat parameter"
        assert "lon" in param_names, "Should have lon parameter"
        
        print("✓ Weather API with local spec successful")
        return True
        
    except Exception as e:
        print(f"✗ Weather API with local spec failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_multiple_auth_methods():
    """Test custom headers combined with OAuth configuration."""
    print("Testing multiple auth methods...")
    
    try:
        # Set up environment with both custom headers and OAuth
        os.environ["OPENAPI_URL"] = "./test/fixtures/petstore.json"
        os.environ["SERVER_NAME"] = "test_multi_auth"
        os.environ["MCP_AUTH_HEADERS"] = '{"X-API-Key": "custom-key"}'
        os.environ["OAUTH_CLIENT_ID"] = "test-client"
        os.environ["OAUTH_CLIENT_SECRET"] = "test-secret"
        os.environ["OAUTH_TOKEN_URL"] = "https://test.com/oauth/token"
        
        config = ServerConfig()
        
        # Verify both auth methods are configured
        assert config.has_custom_headers(), "Should have custom headers"
        assert config.is_oauth_configured(), "Should have OAuth configured"
        
        # Create auth manager
        auth_manager = AuthenticationManager(config)
        assert auth_manager.is_configured(), "Auth manager should be configured"
        
        # Test header application
        request_headers = {"Content-Type": "application/json"}
        updated = auth_manager.add_auth_headers(request_headers)
        
        # Custom headers should be applied
        assert "X-API-Key" in updated, "Should have API key"
        assert updated["X-API-Key"] == "custom-key", "API key should match"
        assert "Content-Type" in updated, "Should preserve existing headers"
        
        print("✓ Multiple auth methods work together")
        return True
        
    except Exception as e:
        print(f"✗ Multiple auth methods test failed: {e}")
        return False
    finally:
        # Clean up environment
        os.environ.pop("MCP_AUTH_HEADERS", None)
        os.environ.pop("OAUTH_CLIENT_ID", None)
        os.environ.pop("OAUTH_CLIENT_SECRET", None)
        os.environ.pop("OAUTH_TOKEN_URL", None)


async def test_relative_path_spec_loading():
    """Test loading spec from different relative paths."""
    print("Testing relative path spec loading...")
    
    try:
        original_dir = os.getcwd()
        
        # Test from project root
        os.environ["OPENAPI_URL"] = "./test/fixtures/weather.yaml"
        os.environ["SERVER_NAME"] = "test_relative"
        
        config = ServerConfig()
        auth_headers = None
        spec = OpenAPILoader.load_spec(config.openapi_url, auth_headers)
        
        assert spec["info"]["title"] == "Test Weather API", "Should load from project root"
        
        # Change to test directory and use different relative path
        os.chdir(os.path.dirname(__file__))
        os.environ["OPENAPI_URL"] = "./fixtures/petstore.json"
        
        config2 = ServerConfig()
        spec2 = OpenAPILoader.load_spec(config2.openapi_url, auth_headers)
        
        assert spec2["info"]["title"] == "Test Petstore API", "Should load from test dir"
        
        os.chdir(original_dir)
        
        print("✓ Relative path spec loading works")
        return True
        
    except Exception as e:
        print(f"✗ Relative path test failed: {e}")
        os.chdir(original_dir)
        return False


async def test_error_handling_invalid_local_spec():
    """Test error handling for invalid local spec."""
    print("Testing error handling for invalid local spec...")
    
    try:
        # Try to load invalid spec
        os.environ["OPENAPI_URL"] = "./test/fixtures/invalid.json"
        os.environ["SERVER_NAME"] = "test_invalid"
        
        config = ServerConfig()
        server = FastMCPOpenAPIServer(config)
        
        try:
            await server.initialize()
            print("✗ Should have raised error for invalid spec")
            return False
        except Exception as e:
            assert "Missing required properties" in str(e), "Should mention missing properties"
            print("✓ Invalid spec error handled correctly")
            return True
            
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
        return False


async def test_spec_with_auth_headers_loading():
    """Test that auth headers are passed when loading remote specs."""
    print("Testing auth headers passed to spec loading...")
    
    try:
        # This tests that the infrastructure is in place
        # We can't actually test remote loading without a real server
        os.environ["OPENAPI_URL"] = "./test/fixtures/petstore.json"  # Use local for testing
        os.environ["SERVER_NAME"] = "test_auth_load"
        os.environ["MCP_AUTH_HEADERS"] = '{"Authorization": "Bearer test-token"}'
        
        config = ServerConfig()
        server = FastMCPOpenAPIServer(config)
        
        # Verify authenticator is set up
        assert server.authenticator is not None, "Should have authenticator"
        
        # Get headers that would be passed
        custom_headers = server.authenticator.get_custom_headers()
        assert "Authorization" in custom_headers, "Should have Authorization header"
        
        # Initialize (this will pass headers to load_spec)
        await server.initialize()
        
        # If we made it here, headers were passed correctly
        print("✓ Auth headers infrastructure correct")
        return True
        
    except Exception as e:
        print(f"✗ Auth headers loading test failed: {e}")
        return False
    finally:
        os.environ.pop("MCP_AUTH_HEADERS", None)


async def run_all_tests():
    """Run all integration tests."""
    print("\n" + "="*50)
    print("Integration Tests - Local Files & Custom Auth")
    print("="*50 + "\n")
    
    tests = [
        test_local_spec_with_custom_auth,
        test_weather_api_with_local_spec,
        test_multiple_auth_methods,
        test_relative_path_spec_loading,
        test_error_handling_invalid_local_spec,
        test_spec_with_auth_headers_loading
    ]
    
    results = []
    for test in tests:
        try:
            success = await test()
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
        print("✓ All integration tests passed!")
        return True
    else:
        print(f"✗ {total - passed} tests failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)