#!/usr/bin/env python3
"""
Simple demo of the FastMCP OpenAPI server.
Shows how to run the server with stdio transport.

Run with: python examples/demo_fastmcp_simple.py
Or after pip install: openapi-mcp
"""

import asyncio
import os
import sys

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


async def main() -> None:
    """Main demo function."""

    # Configure for Norwegian Weather API (no auth required)
    os.environ.update(
        {
            "OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger",
            "SERVER_NAME": "weather_fastmcp",
            "MCP_HTTP_ENABLED": "false",  # Use stdio transport
        }
    )

    print("FastMCP OpenAPI Server Demo")
    print("=" * 30)
    print("API: Norwegian Weather Service")
    print("Transport: stdio (for MCP clients)")
    print("=" * 30)

    # Create and initialize server
    config = ServerConfig()
    server = FastMCPOpenAPIServer(config)
    await server.initialize()

    print(f"✓ Server initialized with {len(server.operations)} operations")
    print("✓ Ready for MCP client connections")
    print("\nTo use with Claude Desktop, add this to your MCP config:")
    print(
        f"""
{{
  "mcpServers": {{
    "weather": {{
      "command": "{sys.executable}",
      "args": ["{os.path.abspath(__file__)}"],
      "transport": "stdio"
    }}
  }}
}}
"""
    )

    # For demo, just show what tools are available
    print(f"\nAvailable tools ({len(server.operations)}):")
    for tool in server.operations[:10]:  # Show first 10
        print(f"  - {config.server_name}_{tool.operation_id}")

    if len(server.operations) > 10:
        print(f"  ... and {len(server.operations) - 10} more tools")

    print("\nStarting stdio server...")
    # This will run the server with stdio transport
    await server.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
