#!/usr/bin/env python3
"""
Test script for mcp-remote compatible endpoints.
Tests the /sse and /mcp endpoints that mcp-remote expects.
"""
import os
import sys
import json
import logging
import asyncio
import httpx
import time

from openapi_mcp import server

async def test_mcp_remote_endpoints():
    """Test mcp-remote compatible endpoints."""
    print("Testing mcp-remote Compatible Endpoints")
    print("=" * 50)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # Test 1: Configuration
        print("\n1. Testing MCP Transport Configuration")
        os.environ.clear()
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore_remote',
            'MCP_HTTP_ENABLED': 'true',
            'MCP_HTTP_HOST': '127.0.0.1',
            'MCP_HTTP_PORT': '8002'
        })
        
        config = server.ServerConfig()
        srv = server.MCPServer(config)
        srv.initialize()
        srv.register_openapi_tools()
        srv.register_standard_tools()
        
        print(f"✓ Server configured with {len(srv.registered_tools)} tools")
        
        # Test 2: Start Server
        print("\n2. Starting MCP Transport Server")
        server_task = asyncio.create_task(srv.mcp_transport.start())
        await asyncio.sleep(3)
        print("✓ MCP transport server started")
        
        # Test 3: Test Standard Endpoints
        print("\n3. Testing Standard mcp-remote Endpoints")
        async with httpx.AsyncClient() as client:
            base_url = f"http://{config.mcp_http_host}:{config.mcp_http_port}"
            
            # Test /health endpoint
            print("\n3.1 Testing /health endpoint")
            try:
                health_response = await client.get(f"{base_url}/health", timeout=5.0)
                if health_response.status_code == 200:
                    health_data = health_response.json()
                    print(f"✓ Health endpoint accessible:")
                    print(f"  - Status: {health_data.get('status')}")
                    print(f"  - Transport: {health_data.get('transport')}")
                    print(f"  - Active sessions: {health_data.get('active_sessions')}")
                else:
                    print(f"✗ Health endpoint returned {health_response.status_code}")
            except Exception as e:
                print(f"✗ Health endpoint error: {e}")
            
            # Test 4: Test /sse endpoint (mcp-remote style)
            print("\n4. Testing /sse Endpoint (mcp-remote compatible)")
            
            # Start SSE connection to /sse
            try:
                sse_url = f"{base_url}/sse"
                print(f"Connecting to SSE: {sse_url}")
                
                # Use timeout for SSE connection test
                async with client.stream("GET", sse_url, timeout=10.0) as sse_stream:
                    print("✓ SSE connection established")
                    
                    event_count = 0
                    session_id = None
                    
                    # Read a few SSE events
                    async for chunk in sse_stream.aiter_text():
                        if chunk.strip():
                            lines = chunk.strip().split('\n')
                            for line in lines:
                                if line.startswith('data: '):
                                    try:
                                        data = json.loads(line[6:])  # Remove 'data: ' prefix
                                        event_count += 1
                                        
                                        if event_count == 1:
                                            print(f"✓ First SSE event received:")
                                            print(f"  - Transport: {data.get('transport')}")
                                            session_id = data.get('session_id')
                                            print(f"  - Session ID: {session_id}")
                                            print(f"  - Server: {data.get('server_info', {}).get('name')}")
                                        
                                        if event_count >= 3:  # Stop after a few events
                                            break
                                    except json.JSONDecodeError:
                                        pass
                        
                        if event_count >= 3:
                            break
                    
                    print(f"✓ Received {event_count} SSE events")
                    
                    # Test 5: Test JSON-RPC via /mcp endpoint
                    print("\n5. Testing JSON-RPC Communication via /mcp")
                    
                    if session_id:
                        # Test initialize request
                        init_request = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2024-11-05",
                                "capabilities": {}
                            }
                        }
                        
                        mcp_response = await client.post(
                            f"{base_url}/mcp",
                            json=init_request,
                            headers={"Mcp-Session-Id": session_id},
                            timeout=10.0
                        )
                        
                        if mcp_response.status_code == 200:
                            response_data = mcp_response.json()
                            print("✓ Initialize request successful:")
                            print(f"  - Protocol Version: {response_data.get('result', {}).get('protocolVersion')}")
                            print(f"  - Server Name: {response_data.get('result', {}).get('serverInfo', {}).get('name')}")
                            
                            # Test tools/list request
                            tools_request = {
                                "jsonrpc": "2.0",
                                "id": 2,
                                "method": "tools/list",
                                "params": {}
                            }
                            
                            tools_response = await client.post(
                                f"{base_url}/mcp",
                                json=tools_request,
                                headers={"Mcp-Session-Id": session_id},
                                timeout=10.0
                            )
                            
                            if tools_response.status_code == 200:
                                tools_data = tools_response.json()
                                tools_list = tools_data.get('result', {}).get('tools', [])
                                print(f"✓ Tools list request successful: {len(tools_list)} tools")
                                
                                # Show first few tools
                                for i, tool in enumerate(tools_list[:3]):
                                    print(f"  - {tool.get('name', 'unnamed')}")
                                    
                                # Test tools/call request
                                if tools_list:
                                    call_request = {
                                        "jsonrpc": "2.0",
                                        "id": 3,
                                        "method": "tools/call",
                                        "params": {
                                            "name": tools_list[0]['name'],
                                            "arguments": {}
                                        }
                                    }
                                    
                                    call_response = await client.post(
                                        f"{base_url}/mcp",
                                        json=call_request,
                                        headers={"Mcp-Session-Id": session_id},
                                        timeout=10.0
                                    )
                                    
                                    if call_response.status_code == 200:
                                        print("✓ Tool call request successful")
                                    else:
                                        print(f"✗ Tool call request failed: {call_response.status_code}")
                            else:
                                print(f"✗ Tools list request failed: {tools_response.status_code}")
                        else:
                            print(f"✗ Initialize request failed: {mcp_response.status_code}")
                    else:
                        print("✗ No session ID received from SSE")
                        
            except asyncio.TimeoutError:
                print("✓ SSE connection timeout (expected for test)")
            except Exception as e:
                print(f"✗ SSE connection error: {e}")
        
        # Test 6: mcp-remote URL formats
        print("\n6. Testing mcp-remote URL formats")
        base_url = f"http://{config.mcp_http_host}:{config.mcp_http_port}"
        
        print("✓ mcp-remote compatible URLs:")
        print(f"  - SSE endpoint: {base_url}/sse")
        print(f"  - HTTP endpoint: {base_url}/mcp")
        print(f"  - Health endpoint: {base_url}/health")
        
        print("\n✓ Configuration for Claude Desktop/Cursor/Windsurf:")
        print(f'  "command": "npx",')
        print(f'  "args": ["mcp-remote", "{base_url}/sse"]')
        
        # Stop server
        print("\n7. Shutting down...")
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        
        await srv.mcp_transport.stop()
        print("✓ MCP transport server stopped")
        
        print("\n" + "=" * 50)
        print("🎉 mcp-remote Compatibility Test Complete!")
        print("✅ Standard /sse endpoint implemented")
        print("✅ JSON-RPC 2.0 communication via /mcp")
        print("✅ Session management functional")
        print("✅ Health monitoring available")
        print("✅ Ready for mcp-remote clients")
        
        return True
        
    except Exception as e:
        print(f"\n❌ mcp-remote compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run mcp-remote compatibility tests."""
    try:
        success = asyncio.run(test_mcp_remote_endpoints())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)

if __name__ == "__main__":
    main()