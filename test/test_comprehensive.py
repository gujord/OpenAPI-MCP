#!/usr/bin/env python3
"""
Comprehensive test script for the OpenAPI-MCP server.
Tests multiple APIs and authentication methods.
"""
import os
import sys
import logging
import asyncio
import pytest

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


@pytest.mark.asyncio
async def test_comprehensive():
    """Run comprehensive tests across multiple APIs."""
    print("Comprehensive OpenAPI-MCP Server Testing")
    print("=" * 50)

    # Set up logging
    logging.basicConfig(level=logging.ERROR, format="%(levelname)s: %(message)s")

    test_results = []

    # Save original env
    original_env = os.environ.copy()

    try:
        # Test 1: Petstore API (Basic functionality)
        print("\n1. Testing Petstore API (No Authentication)")
        try:
            os.environ.clear()
            os.environ.update(
                {"OPENAPI_URL": "https://petstore3.swagger.io/api/v3/openapi.json", "SERVER_NAME": "petstore3"}
            )

            config = ServerConfig()
            srv = FastMCPOpenAPIServer(config)
            await srv.initialize()

            # Find the findPetsByStatus tool
            find_pets_tool = None
            for op in srv.operations:
                if "findPetsByStatus" in op.operation_id:
                    find_pets_tool = op
                    break

            assert find_pets_tool is not None

            # Test a real API call
            tool_func = srv._create_tool_function(find_pets_tool)
            result = await tool_func(status="available")

            success = "result" in result and "data" in result["result"]
            test_results.append(("Petstore API", success, f"{len(srv.operations)} operations"))
            print(f"  Petstore: {len(srv.operations)} operations registered")

        except Exception as e:
            test_results.append(("Petstore API", False, str(e)))
            print(f"  Petstore failed: {e}")

        # Test 2: Norwegian Weather API (Real-world example)
        print("\n2. Testing Norwegian Weather API")
        try:
            os.environ.clear()
            os.environ.update(
                {"OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger", "SERVER_NAME": "weather"}
            )

            config = ServerConfig()
            srv = FastMCPOpenAPIServer(config)
            await srv.initialize()

            # Find compact tool
            compact_tool = None
            for op in srv.operations:
                if "compact" in op.operation_id.lower():
                    compact_tool = op
                    break

            assert compact_tool is not None

            # Test weather forecast for Oslo
            tool_func = srv._create_tool_function(compact_tool)
            result = await tool_func(lat=59.9139, lon=10.7522)

            success = "result" in result and "data" in result["result"]
            if success and "properties" in result["result"]["data"]:
                weather_data = result["result"]["data"]["properties"]
                forecast_count = len(weather_data.get("timeseries", []))
                test_results.append(("Weather API", True, f"{len(srv.operations)} operations, {forecast_count} forecasts"))
                print(f"  Weather: {len(srv.operations)} operations, {forecast_count} forecast periods")
            else:
                test_results.append(("Weather API", False, "No weather data"))
                print("  Weather: No data received")

        except Exception as e:
            test_results.append(("Weather API", False, str(e)))
            print(f"  Weather failed: {e}")

        # Test 3: Authentication Configuration (Without real credentials)
        print("\n3. Testing Authentication Configuration")
        try:
            # Test OAuth configuration
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

            config_oauth = ServerConfig()
            srv_oauth = FastMCPOpenAPIServer(config_oauth)
            oauth_configured = srv_oauth.authenticator.is_configured()

            # Test username/password configuration
            os.environ.update(
                {
                    "API_USERNAME": "test_user",
                    "API_PASSWORD": "test_pass",
                    "API_LOGIN_ENDPOINT": "https://example.com/auth/token",
                }
            )

            config_user = ServerConfig()
            srv_user = FastMCPOpenAPIServer(config_user)
            user_auth_configured = srv_user.authenticator.is_configured()

            auth_success = oauth_configured and user_auth_configured
            test_results.append(("Authentication Config", auth_success, "OAuth & Username/Password"))
            print(f"  Authentication: OAuth={oauth_configured}, Username/Password={user_auth_configured}")

        except Exception as e:
            test_results.append(("Authentication Config", False, str(e)))
            print(f"  Authentication failed: {e}")

        # Test 4: Error Handling and Edge Cases
        print("\n4. Testing Error Handling")
        try:
            os.environ.clear()
            os.environ.update(
                {"OPENAPI_URL": "https://petstore3.swagger.io/api/v3/openapi.json", "SERVER_NAME": "error_test"}
            )

            config = ServerConfig()
            srv = FastMCPOpenAPIServer(config)
            await srv.initialize()

            # Find getPetById tool
            get_pet_tool = None
            for op in srv.operations:
                if "getPetById" in op.operation_id:
                    get_pet_tool = op
                    break

            assert get_pet_tool is not None

            # Test missing required parameters
            tool_func = srv._create_tool_function(get_pet_tool)
            error_result = await tool_func()  # Missing required petId

            has_help = "result" in error_result and "help" in error_result["result"]

            error_success = has_help
            test_results.append(("Error Handling", error_success, "Parameter validation"))
            print(f"  Error Handling: Parameter validation={has_help}")

        except Exception as e:
            test_results.append(("Error Handling", False, str(e)))
            print(f"  Error handling failed: {e}")

        # Summary
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)

        passed = 0
        for test_name, success, details in test_results:
            status = "PASS" if success else "FAIL"
            print(f"{status} {test_name}: {details}")
            if success:
                passed += 1

        print(f"\nResults: {passed}/{len(test_results)} tests passed")

        assert passed == len(test_results), f"{len(test_results) - passed} tests failed"

    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


if __name__ == "__main__":
    asyncio.run(test_comprehensive())
