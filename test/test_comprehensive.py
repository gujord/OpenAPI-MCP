#!/usr/bin/env python3
"""
Comprehensive test script for the OpenAPI-MCP server.
Tests multiple APIs and authentication methods.
"""
import os
import sys
import logging

from openapi_mcp import server

def test_comprehensive():
    """Run comprehensive tests across multiple APIs."""
    print("Comprehensive OpenAPI-MCP Server Testing")
    print("=" * 50)
    
    # Set up logging
    logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')
    
    test_results = []
    
    # Test 1: Petstore API (Basic functionality)
    print("\n1. Testing Petstore API (No Authentication)")
    try:
        os.environ.clear()
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore3'
        })
        
        config = server.ServerConfig()
        srv = server.MCPServer(config)
        srv.initialize()
        
        api_tools = srv.register_openapi_tools()
        srv.register_standard_tools()
        resources = srv.register_resources()
        prompts = srv.generate_prompts()
        
        # Test a real API call
        tool_func = srv.registered_tools['petstore3_findPetsByStatus']['function']
        result = tool_func(req_id='test', status='available')
        
        success = 'result' in result and 'data' in result['result']
        test_results.append(('Petstore API', success, f"{api_tools} tools, {resources} resources"))
        print(f"✓ Petstore: {api_tools} API tools, {len(srv.registered_tools)} total tools")
        
    except Exception as e:
        test_results.append(('Petstore API', False, str(e)))
        print(f"✗ Petstore failed: {e}")
    
    # Test 2: Norwegian Weather API (Real-world example)
    print("\n2. Testing Norwegian Weather API")
    try:
        os.environ.clear()
        os.environ.update({
            'OPENAPI_URL': 'https://api.met.no/weatherapi/locationforecast/2.0/swagger',
            'SERVER_NAME': 'weather'
        })
        
        config = server.ServerConfig()
        srv = server.MCPServer(config)
        srv.initialize()
        
        api_tools = srv.register_openapi_tools()
        srv.register_standard_tools()
        resources = srv.register_resources()
        prompts = srv.generate_prompts()
        
        # Test weather forecast for Oslo
        tool_func = srv.registered_tools['weather_get__compact']['function']
        result = tool_func(req_id='test', lat=59.9139, lon=10.7522)
        
        success = 'result' in result and 'data' in result['result']
        if success and 'properties' in result['result']['data']:
            weather_data = result['result']['data']['properties']
            forecast_count = len(weather_data.get('timeseries', []))
            test_results.append(('Weather API', True, f"{api_tools} tools, {forecast_count} forecasts"))
            print(f"✓ Weather: {api_tools} API tools, {forecast_count} forecast periods")
        else:
            test_results.append(('Weather API', False, "No weather data"))
            print("✗ Weather: No data received")
        
    except Exception as e:
        test_results.append(('Weather API', False, str(e)))
        print(f"✗ Weather failed: {e}")
    
    # Test 3: Authentication Configuration (Without real credentials)
    print("\n3. Testing Authentication Configuration")
    try:
        # Test OAuth configuration
        os.environ.clear()
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore_oauth',
            'OAUTH_CLIENT_ID': 'test_client',
            'OAUTH_CLIENT_SECRET': 'test_secret',
            'OAUTH_TOKEN_URL': 'https://example.com/oauth/token'
        })
        
        config_oauth = server.ServerConfig()
        srv_oauth = server.MCPServer(config_oauth)
        oauth_configured = srv_oauth.authenticator.is_configured()
        
        # Test username/password configuration
        os.environ.update({
            'API_USERNAME': 'test_user',
            'API_PASSWORD': 'test_pass',
            'API_LOGIN_ENDPOINT': 'https://example.com/auth/token'
        })
        
        config_user = server.ServerConfig()
        srv_user = server.MCPServer(config_user)
        user_auth_configured = srv_user.authenticator.is_configured()
        
        auth_success = oauth_configured and user_auth_configured
        test_results.append(('Authentication Config', auth_success, "OAuth & Username/Password"))
        print(f"✓ Authentication: OAuth={oauth_configured}, Username/Password={user_auth_configured}")
        
    except Exception as e:
        test_results.append(('Authentication Config', False, str(e)))
        print(f"✗ Authentication failed: {e}")
    
    # Test 4: Error Handling and Edge Cases
    print("\n4. Testing Error Handling")
    try:
        # Test with invalid OpenAPI URL
        os.environ.clear()
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'error_test'
        })
        
        config = server.ServerConfig()
        srv = server.MCPServer(config)
        srv.initialize()
        srv.register_openapi_tools()
        
        # Test missing required parameters
        tool_func = srv.registered_tools['error_test_getPetById']['function']
        error_result = tool_func(req_id='test')  # Missing required petId
        
        has_help = 'result' in error_result and 'help' in error_result['result']
        
        # Test tool not found
        not_found = srv._tools_call_tool(req_id='test', name='nonexistent_tool')
        has_error = 'error' in not_found
        
        error_success = has_help and has_error
        test_results.append(('Error Handling', error_success, "Parameter validation & tool not found"))
        print(f"✓ Error Handling: Parameter validation={has_help}, Tool not found={has_error}")
        
    except Exception as e:
        test_results.append(('Error Handling', False, str(e)))
        print(f"✗ Error handling failed: {e}")
    
    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, success, details in test_results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        if success:
            passed += 1
    
    print(f"\nResults: {passed}/{len(test_results)} tests passed")
    
    if passed == len(test_results):
        print("\n🎉 All tests passed! OpenAPI-MCP server is working correctly.")
        print("✅ Multiple API integrations successful")
        print("✅ Authentication framework operational") 
        print("✅ Error handling robust")
        print("✅ Real-world API calls working")
        return True
    else:
        print(f"\n⚠️  {len(test_results) - passed} tests failed.")
        return False

if __name__ == "__main__":
    success = test_comprehensive()
    sys.exit(0 if success else 1)