#!/usr/bin/env python3
"""
Test script to validate the enhanced authentication functionality.
"""
import os
import sys
import logging
import asyncio
import pytest

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


@pytest.mark.asyncio
async def test_authentication_configuration():
    """Test authentication configuration and setup."""
    print("Testing Enhanced Authentication System")
    print("=" * 50)

    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Test 1: OAuth Configuration
    print("\n1. Testing OAuth Configuration")
    # Save original env
    original_env = os.environ.copy()

    try:
        os.environ.clear()
        os.environ.update(
            {
                "OPENAPI_URL": "https://petstore3.swagger.io/api/v3/openapi.json",
                "SERVER_NAME": "petstore_oauth",
                "OAUTH_CLIENT_ID": "test_client",
                "OAUTH_CLIENT_SECRET": "test_secret",
                "OAUTH_TOKEN_URL": "https://example.com/oauth/token",
            }
        )

        config1 = ServerConfig()
        assert config1.is_oauth_configured() is True
        print(f"  OAuth configured: {config1.is_oauth_configured()}")
        print(f"  - Client ID: {config1.oauth_client_id}")
        print(f"  - Token URL: {config1.oauth_token_url}")

        # Test 2: Username/Password Configuration
        print("\n2. Testing Username/Password Configuration")
        os.environ.clear()
        os.environ.update(
            {
                "OPENAPI_URL": "https://api.example.com/openapi.json",
                "SERVER_NAME": "secure_api",
                "API_USERNAME": "admin",
                "API_PASSWORD": "test123",
                "API_LOGIN_ENDPOINT": "https://api.example.com/auth/token",
            }
        )

        config2 = ServerConfig()
        assert config2.is_username_auth_configured() is True
        print(f"  Username/password configured: {config2.is_username_auth_configured()}")
        print(f"  - Username: {config2.username}")
        print(f"  - Login endpoint: {config2.login_endpoint}")

        # Test 3: Authentication Manager Integration with FastMCPOpenAPIServer
        print("\n3. Testing Authentication Manager")
        srv = FastMCPOpenAPIServer(config2)
        assert srv.authenticator.is_configured() is True
        print(f"  Auth manager created: {srv.authenticator.is_configured()}")

        # Test 4: Integration with Weather API
        print("\n4. Testing Integration with Norwegian Weather API")
        os.environ.update(
            {
                "OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger",
                "SERVER_NAME": "weather",
                "API_USERNAME": "test_user",
                "API_PASSWORD": "test123",
            }
        )

        config4 = ServerConfig()
        srv4 = FastMCPOpenAPIServer(config4)
        await srv4.initialize()

        print(f"  API operations parsed: {len(srv4.operations)}")
        assert len(srv4.operations) > 0

        # Test weather forecast tools
        forecast_tools = [op.operation_id for op in srv4.operations if "compact" in op.operation_id.lower() or "complete" in op.operation_id.lower()]
        print(f"  Weather forecast tools: {len(forecast_tools)}")
        for tool in forecast_tools[:3]:
            print(f"  - {tool}")

        # Test 5: Environment Variable Documentation
        print("\n5. Environment Variables Supported:")
        print("  Core Configuration:")
        print("  - OPENAPI_URL (required)")
        print("  - SERVER_NAME (optional)")
        print("  OAuth2 Authentication:")
        print("  - OAUTH_CLIENT_ID")
        print("  - OAUTH_CLIENT_SECRET")
        print("  - OAUTH_TOKEN_URL")
        print("  - OAUTH_SCOPE")
        print("  Username/Password Authentication:")
        print("  - API_USERNAME")
        print("  - API_PASSWORD")
        print("  - API_LOGIN_ENDPOINT (optional, auto-detected)")

        print("\n" + "=" * 50)
        print("All authentication tests passed!")

    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


if __name__ == "__main__":
    asyncio.run(test_authentication_configuration())
