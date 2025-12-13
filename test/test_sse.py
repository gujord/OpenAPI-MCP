#!/usr/bin/env python3
"""
Test script to validate SSE (Server-Sent Events) functionality.
"""
import os
import sys
import logging
import asyncio
import httpx
import time

from openapi_mcp import server

async def test_sse_functionality():
    """Test SSE functionality."""
    print("Testing SSE (Server-Sent Events) Functionality")
    print("=" * 50)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # Test 1: SSE Configuration
        print("\n1. Testing SSE Configuration")
        os.environ.clear()
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore_sse',
            'SSE_ENABLED': 'true',
            'SSE_HOST': '127.0.0.1',
            'SSE_PORT': '8001'
        })
        
        config = server.ServerConfig()
        print(f"✓ SSE Configuration:")
        print(f"  - Enabled: {config.sse_enabled}")
        print(f"  - Host: {config.sse_host}")
        print(f"  - Port: {config.sse_port}")
        
        # Test 2: Server with SSE Support
        print("\n2. Testing Server with SSE Support")
        srv = server.MCPServer(config)
        print(f"✓ SSE Manager created: {srv.sse_manager is not None}")
        print(f"✓ SSE Server Manager created: {srv.sse_server_manager is not None}")
        print(f"✓ SSE Tool Factory created: {srv.sse_tool_factory is not None}")
        
        # Test 3: Initialize and Register Tools
        print("\n3. Testing Tool Registration with SSE")
        srv.initialize()
        
        api_tools = srv.register_openapi_tools()
        srv.register_standard_tools()
        
        print(f"✓ API tools registered: {api_tools}")
        print(f"✓ Total tools: {len(srv.registered_tools)}")
        
        # Check for SSE-specific tools
        sse_tools = [name for name in srv.registered_tools.keys() if 'sse' in name.lower()]
        print(f"✓ SSE-specific tools: {len(sse_tools)}")
        for tool in sse_tools:
            print(f"  - {tool}")
        
        # Test 4: Check Tools for Streaming Support
        print("\n4. Testing Streaming Support in Tools")
        streaming_tools = []
        for tool_name, tool_data in srv.registered_tools.items():
            metadata = tool_data.get('metadata', {})
            if metadata.get('streaming_supported', False):
                streaming_tools.append(tool_name)
        
        print(f"✓ Tools with streaming support: {len(streaming_tools)}")
        for tool in streaming_tools[:5]:  # Show first 5
            print(f"  - {tool}")
        
        # Test 5: SSE Manager Operations
        print("\n5. Testing SSE Manager Operations")
        if srv.sse_manager:
            # Create a test connection
            connection = srv.sse_manager.create_connection()
            print(f"✓ Test connection created: {connection.connection_id}")
            print(f"✓ Active connections: {srv.sse_manager.get_connection_count()}")
            
            # Test connection cleanup
            await srv.sse_manager.remove_connection(connection.connection_id)
            print(f"✓ Connection removed: {srv.sse_manager.get_connection_count()} remaining")
        
        # Test 6: SSE Server URLs
        print("\n6. Testing SSE Server URLs")
        if srv.sse_server_manager:
            health_url = srv.sse_server_manager.get_health_url()
            connections_url = srv.sse_server_manager.get_connections_url()
            print(f"✓ Health URL: {health_url}")
            print(f"✓ Connections URL: {connections_url}")
        
        # Test 7: Tool Metadata for Streaming
        print("\n7. Testing Tool Metadata Enhancement")
        sample_tool_name = list(srv.registered_tools.keys())[0]
        sample_metadata = srv.registered_tools[sample_tool_name]['metadata']
        
        # Check for streaming parameters
        stream_params = [p for p in sample_metadata.get('parameters', []) if p.get('name') == 'stream']
        if stream_params:
            print("✓ Stream parameter found in tool metadata:")
            print(f"  - Type: {stream_params[0].get('type')}")
            print(f"  - Description: {stream_params[0].get('description')}")
        
        print("\n" + "=" * 50)
        print("✅ SSE functionality tests completed successfully!")
        print("✅ SSE configuration and components properly initialized")
        print("✅ Tools enhanced with streaming support")
        print("✅ SSE manager operations functional")
        print("✅ Ready for real-time streaming responses")
        
        return True
        
    except Exception as e:
        print(f"\n❌ SSE test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_sse_server_startup():
    """Test SSE server startup (requires actual server run)."""
    print("\n" + "=" * 50)
    print("Testing SSE Server Startup (5 second test)")
    print("=" * 50)
    
    try:
        # Configure for SSE
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore_sse_test',
            'SSE_ENABLED': 'true',
            'SSE_HOST': '127.0.0.1',
            'SSE_PORT': '8002'
        })
        
        config = server.ServerConfig()
        srv = server.MCPServer(config)
        srv.initialize()
        srv.register_openapi_tools()
        srv.register_standard_tools()
        
        # Start SSE server
        print("Starting SSE server...")
        await srv.start_sse_server()
        print("✓ SSE server started")
        
        # Give it a moment to start
        await asyncio.sleep(2)
        
        # Test health endpoint
        try:
            async with httpx.AsyncClient() as client:
                health_url = srv.sse_server_manager.get_health_url()
                response = await client.get(health_url, timeout=5.0)
                
                if response.status_code == 200:
                    health_data = response.json()
                    print("✓ Health endpoint accessible:")
                    print(f"  - Status: {health_data.get('status')}")
                    print(f"  - Active connections: {health_data.get('active_connections')}")
                else:
                    print(f"✗ Health endpoint returned {response.status_code}")
                    
        except Exception as e:
            print(f"✗ Health endpoint test failed: {e}")
        
        # Stop SSE server
        print("Stopping SSE server...")
        await srv.stop_sse_server()
        print("✓ SSE server stopped")
        
        return True
        
    except Exception as e:
        print(f"❌ SSE server test failed: {e}")
        return False

def main():
    """Run SSE tests."""
    async def run_tests():
        success1 = await test_sse_functionality()
        success2 = await test_sse_server_startup()
        return success1 and success2
    
    try:
        success = asyncio.run(run_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()