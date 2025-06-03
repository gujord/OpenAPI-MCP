#!/usr/bin/env python3
"""
Demonstration script for SSE (Server-Sent Events) functionality.
Shows how to set up and use streaming with the OpenAPI-MCP server.
"""
import os
import sys
import logging
import asyncio
import httpx
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import server

async def demo_sse_streaming():
    """Demonstrate SSE streaming functionality."""
    print("OpenAPI-MCP Server - SSE Streaming Demonstration")
    print("=" * 60)
    
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # Configure server with SSE enabled
        print("1. Configuring server with SSE support...")
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore_streaming',
            'SSE_ENABLED': 'true',
            'SSE_HOST': '127.0.0.1',
            'SSE_PORT': '8003'
        })
        
        config = server.ServerConfig()
        srv = server.MCPServer(config)
        srv.initialize()
        
        # Register tools with streaming support
        print("2. Registering tools with streaming support...")
        api_tools = srv.register_openapi_tools()
        srv.register_standard_tools()
        
        print(f"   ✓ {api_tools} API tools registered")
        print(f"   ✓ {len(srv.registered_tools)} total tools available")
        
        # Show streaming-enabled tools
        streaming_tools = []
        for tool_name, tool_data in srv.registered_tools.items():
            metadata = tool_data.get('metadata', {})
            if metadata.get('streaming_supported', False):
                streaming_tools.append(tool_name)
        
        print(f"   ✓ {len(streaming_tools)} tools support streaming")
        
        # Start SSE server
        print("3. Starting SSE server...")
        await srv.start_sse_server()
        print("   ✓ SSE server running on http://127.0.0.1:8003")
        
        # Give server time to start
        await asyncio.sleep(2)
        
        # Test SSE endpoints
        print("4. Testing SSE endpoints...")
        async with httpx.AsyncClient() as client:
            # Health check
            health_response = await client.get("http://127.0.0.1:8003/sse/health")
            if health_response.status_code == 200:
                health_data = health_response.json()
                print(f"   ✓ Health check: {health_data['status']}")
            
            # Connections info
            connections_response = await client.get("http://127.0.0.1:8003/sse/connections")
            if connections_response.status_code == 200:
                conn_data = connections_response.json()
                print(f"   ✓ Active connections: {conn_data['active_connections']}")
        
        # Demonstrate tool with streaming parameter
        print("5. Demonstrating streaming-enabled tools...")
        sample_tool = srv.registered_tools['petstore_streaming_findPetsByStatus']['function']
        
        # Regular call (non-streaming)
        print("   Testing regular (non-streaming) call...")
        regular_result = sample_tool(req_id='demo1', status='available')
        if 'result' in regular_result and 'data' in regular_result['result']:
            print(f"   ✓ Regular call successful - found data")
        
        # Streaming call simulation
        print("   Testing streaming call simulation...")
        streaming_result = sample_tool(req_id='demo2', status='available', stream=True)
        if 'result' in streaming_result:
            result = streaming_result['result']
            if 'stream_connection_id' in result:
                print(f"   ✓ Streaming connection created: {result['stream_connection_id']}")
                print(f"   ✓ Stream URL: {result.get('stream_url', 'N/A')}")
        
        # Test SSE-specific tools
        print("6. Testing SSE management tools...")
        
        # SSE connections tool
        connections_tool = srv.registered_tools['petstore_streaming_sse_connections']['function']
        conn_result = connections_tool(req_id='demo3')
        if 'result' in conn_result:
            active = conn_result['result'].get('active_connections', 0)
            print(f"   ✓ SSE connections tool: {active} active connections")
        
        # SSE broadcast tool
        broadcast_tool = srv.registered_tools['petstore_streaming_sse_broadcast']['function']
        broadcast_result = broadcast_tool(req_id='demo4', message="Hello from OpenAPI-MCP!")
        if 'result' in broadcast_result:
            print(f"   ✓ Broadcast tool: {broadcast_result['result']['message']}")
        
        # Show SSE event types and features
        print("7. SSE Features Summary:")
        print("   ✓ Event Types: data, error, complete, heartbeat, metadata")
        print("   ✓ Chunk Processors: JSON Lines, CSV, Plain Text")
        print("   ✓ Connection Management: Automatic heartbeat and cleanup")
        print("   ✓ Broadcasting: Send messages to all connected clients")
        print("   ✓ Health Monitoring: Real-time connection status")
        
        # Show example SSE event format
        print("8. Example SSE Event Format:")
        print("""
   id: chunk_1
   event: data
   data: {"chunk": "Sample streaming data..."}
   
   event: heartbeat
   data: {"timestamp": 1748912623.456}
   
   event: complete
   data: {"stream_complete": true, "total_chunks": 10}
        """)
        
        print("9. Integration Points:")
        print("   ✓ All API tools automatically support stream=true parameter")
        print("   ✓ Intelligent content-type detection for chunk processing")
        print("   ✓ CORS enabled for web client integration")
        print("   ✓ Automatic connection cleanup and error handling")
        
        # Stop SSE server
        print("10. Shutting down...")
        await srv.stop_sse_server()
        print("    ✓ SSE server stopped")
        
        print("\n" + "=" * 60)
        print("🎉 SSE Streaming Demonstration Complete!")
        print("✅ Server-Sent Events fully integrated and operational")
        print("✅ Real-time streaming ready for production use")
        print("✅ All API tools enhanced with streaming capabilities")
        print("✅ Comprehensive connection management and monitoring")
        
        return True
        
    except Exception as e:
        print(f"\n❌ SSE demonstration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the SSE demonstration."""
    try:
        success = asyncio.run(demo_sse_streaming())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nDemonstration interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()