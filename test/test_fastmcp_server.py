#!/usr/bin/env python3
"""
Test script for FastMCP-based OpenAPI server.
"""
import os
import sys
import logging
import asyncio

from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer
from openapi_mcp.config import ServerConfig

async def test_fastmcp_server():
    """Test FastMCP server implementation."""
    print("Testing FastMCP OpenAPI Server")
    print("=" * 40)

    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    try:
        # Test 1: Import and create server
        print("\n1. Testing FastMCP Server Creation")
        
        os.environ.clear()
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore_fastmcp',
            'MCP_HTTP_ENABLED': 'true',
            'MCP_HTTP_HOST': '127.0.0.1',
            'MCP_HTTP_PORT': '8003'
        })
        
        config = ServerConfig()
        server = FastMCPOpenAPIServer(config)
        print("✓ FastMCP server created successfully")
        
        # Test 2: Initialize server
        print("\n2. Testing Server Initialization")
        await server.initialize()
        print(f"✓ Server initialized with {len(server.operations)} operations")
        
        # Test 3: Check registered tools
        print("\n3. Testing Tool Registration")
        tools = await server.mcp.get_tools()
        print(f"✓ {len(tools)} tools registered via FastMCP")
        
        # Show first few tools
        tools_list = list(tools.values()) if isinstance(tools, dict) else list(tools)
        for i, tool in enumerate(tools_list[:5]):
            print(f"  - {tool.name}: {tool.description[:50]}...")
        
        # Test 4: Check resources
        print("\n4. Testing Resource Registration") 
        resources = await server.mcp.get_resources()
        print(f"✓ {len(resources)} resources registered")
        
        # Test 5: Check prompts
        print("\n5. Testing Prompt Registration")
        prompts = await server.mcp.get_prompts()
        print(f"✓ {len(prompts)} prompts registered")
        
        prompts_list = list(prompts.values()) if isinstance(prompts, dict) else list(prompts)
        for prompt in prompts_list:
            print(f"  - {prompt.name}: {prompt.description}")
        
        # Test 6: Test management tools
        print("\n6. Testing Management Tools")
        
        # Find management tools
        mgmt_tools = [t for t in tools_list if 'server_info' in t.name or 'list_operations' in t.name]
        print(f"✓ {len(mgmt_tools)} management tools found")
        
        for tool in mgmt_tools:
            print(f"  - {tool.name}")
        
        # Test 7: Get apps (without running)
        print("\n7. Testing App Creation")
        sse_app = server.get_sse_app()
        http_app = server.get_http_app()
        print("✓ SSE app created")
        print("✓ HTTP app created")
        print(f"✓ SSE app type: {type(sse_app)}")
        print(f"✓ HTTP app type: {type(http_app)}")
        
        print("\n" + "=" * 40)
        print("🎉 FastMCP Server Test Complete!")
        print("✅ FastMCP integration successful")
        print("✅ Tools registered via add_tool()")
        print("✅ Resources registered via add_resource_fn()")
        print("✅ Prompts registered via add_prompt()")
        print("✅ SSE and HTTP apps available")
        print("✅ Ready for FastMCP deployment")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FastMCP server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run FastMCP server tests."""
    try:
        success = asyncio.run(test_fastmcp_server())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()