#!/usr/bin/env python3
"""
Demo of the FastMCP OpenAPI server with Xquik's public OpenAPI specification.

Set XQUIK_API_KEY before running:
    XQUIK_API_KEY=your-key python examples/demo_xquik_openapi.py
"""
import asyncio
import json
import os
import sys

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


async def main():
    """Run the Xquik OpenAPI demo."""
    api_key = os.environ.get("XQUIK_API_KEY", "YOUR_XQUIK_API_KEY")

    os.environ.update(
        {
            "OPENAPI_URL": "https://xquik.com/openapi.json",
            "SERVER_NAME": "xquik",
            "MCP_AUTH_HEADERS": json.dumps({"Authorization": f"Bearer {api_key}"}),
            "MCP_HTTP_ENABLED": "false",
        }
    )

    print("FastMCP OpenAPI Server Demo")
    print("=" * 30)
    print("API: Xquik")
    print("Transport: stdio")
    print("=" * 30)

    config = ServerConfig()
    server = FastMCPOpenAPIServer(config)
    await server.initialize()

    print(f"Server initialized with {len(server.operations)} operations")
    print("Ready for MCP client connections")
    print("\nTo use with Claude Desktop, add this to your MCP config:")
    print(
        f"""
{{
  "mcpServers": {{
    "xquik": {{
      "command": "{sys.executable}",
      "args": ["{os.path.abspath(__file__)}"],
      "env": {{
        "XQUIK_API_KEY": "YOUR_XQUIK_API_KEY"
      }},
      "transport": "stdio"
    }}
  }}
}}
"""
    )

    tools = await server.mcp.get_tools()
    tools_list = list(tools.values()) if isinstance(tools, dict) else list(tools)
    print(f"\nAvailable tools ({len(tools_list)}):")
    for tool in tools_list[:10]:
        print(f"  - {tool.name}")

    if len(tools_list) > 10:
        print(f"  ... and {len(tools_list) - 10} more tools")

    print("\nStarting stdio server...")
    server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())
