#!/usr/bin/env python3
"""
Demonstration script for SSE (Server-Sent Events) functionality.
Shows how to set up and use SSE transport with the FastMCP OpenAPI server.

Run with: python examples/demo_sse.py
"""
import os
import sys
import logging
import asyncio
import httpx

from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer
from openapi_mcp.config import ServerConfig


async def demo_sse_streaming():
    """Demonstrate SSE streaming functionality with FastMCP."""
    print("OpenAPI-MCP Server - SSE Streaming Demonstration")
    print("=" * 60)

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    try:
        # Configure server with SSE enabled
        print("1. Configuring server with SSE support...")
        os.environ.update({
            'OPENAPI_URL': 'https://petstore3.swagger.io/api/v3/openapi.json',
            'SERVER_NAME': 'petstore_streaming',
            'MCP_HTTP_ENABLED': 'true',
            'MCP_HTTP_HOST': '127.0.0.1',
            'MCP_HTTP_PORT': '8003'
        })

        config = ServerConfig()
        server = FastMCPOpenAPIServer(config)
        await server.initialize()

        print(f"   Operations loaded: {len(server.operations)}")

        # Show available tools
        print("2. Available tools:")
        tools = await server.mcp.get_tools()
        tools_list = list(tools.values()) if isinstance(tools, dict) else list(tools)
        for tool in tools_list[:5]:  # Show first 5
            print(f"   - {tool.name}")
        if len(tools_list) > 5:
            print(f"   ... and {len(tools_list) - 5} more")

        # Start SSE server in background
        print("3. Starting SSE server on http://127.0.0.1:8003...")
        print("   Press Ctrl+C to stop\n")

        # Run SSE server
        await server.run_sse_async(host="127.0.0.1", port=8003)

    except KeyboardInterrupt:
        print("\nSSE server stopped by user")
    except Exception as e:
        print(f"\nSSE demonstration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """Run the SSE demonstration."""
    try:
        success = asyncio.run(demo_sse_streaming())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nDemonstration interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
