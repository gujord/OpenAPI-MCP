#!/usr/bin/env python3
"""
Test script to validate the OpenAPI-MCP server functionality.
"""
import os
import sys
import logging

from openapi_mcp import server

def test_server():
    """Test the OpenAPI-MCP server with Petstore API."""
    print("Testing OpenAPI-MCP Server with Petstore API")
    print("=" * 50)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # Test configuration
        os.environ['OPENAPI_URL'] = 'https://petstore3.swagger.io/api/v3/openapi.json'
        os.environ['SERVER_NAME'] = 'petstore3'
        
        config = server.ServerConfig()
        print(f"✓ Configuration loaded: {config.server_name}")
        
        # Test server initialization
        srv = server.MCPServer(config)
        srv.initialize()
        print(f"✓ Server initialized successfully")
        print(f"  - API: {srv.openapi_spec.get('info', {}).get('title', 'Unknown')}")
        print(f"  - Operations parsed: {len(srv.operations_info)}")
        
        # Test tool registration
        api_tools = srv.register_openapi_tools()
        srv.register_standard_tools()
        print(f"✓ Tools registered: {api_tools} API tools, {len(srv.registered_tools)} total")
        
        # Test resource registration
        resources = srv.register_resources()
        print(f"✓ Resources registered: {resources}")
        
        # Test prompt generation
        prompts = srv.generate_prompts()
        print(f"✓ Prompts generated: {prompts}")
        
        # Test tool listing
        tools_list = srv._tools_list_tool('test-id')
        print(f"✓ Tools list: {len(tools_list['result']['tools'])} tools available")
        
        # Test dry run
        tool_func = srv.registered_tools['petstore3_findPetsByStatus']['function']
        dry_run = tool_func(req_id='test', status='available', dry_run=True)
        print("✓ Dry run test successful")
        print(f"  - URL: {dry_run['result']['request']['url']}")
        print(f"  - Method: {dry_run['result']['request']['method']}")
        
        # Test real API call
        real_call = tool_func(req_id='test', status='available')
        if 'result' in real_call and 'data' in real_call['result']:
            data = real_call['result']['data']
            print(f"✓ Real API call successful: Found {len(data)} pets")
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! Server is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_server()
    sys.exit(0 if success else 1)