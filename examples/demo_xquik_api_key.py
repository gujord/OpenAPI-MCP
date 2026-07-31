#!/usr/bin/env python3
"""
Run the FastMCP OpenAPI server with Xquik's hosted OpenAPI document.

Set XQUIK_API_KEY before running. The demo configures the x-api-key header for
upstream API requests without printing the key.
"""

import asyncio
import json
import os
import sys

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


async def initialize_server() -> FastMCPOpenAPIServer:
    """Initialize the Xquik OpenAPI server."""
    api_key = os.environ.get("XQUIK_API_KEY", "")
    if not api_key:
        raise RuntimeError("Set XQUIK_API_KEY before running this example.")

    os.environ.update(
        {
            "OPENAPI_URL": "https://xquik.com/openapi.json",
            "SERVER_NAME": "xquik_fastmcp",
            "MCP_HTTP_ENABLED": "false",
            "MCP_AUTH_HEADERS": json.dumps({"x-api-key": api_key}),
        }
    )

    config = ServerConfig()
    server = FastMCPOpenAPIServer(config)
    await server.initialize()
    return server


def main() -> None:
    """Initialize Xquik, then serve it to stdio MCP clients."""
    server = asyncio.run(initialize_server())
    print(
        f"Xquik FastMCP server initialized with {len(server.operations)} operations.",
        file=sys.stderr,
    )
    print("Add this command to an MCP client configuration:", file=sys.stderr)
    print(f"{sys.executable} {os.path.abspath(__file__)}", file=sys.stderr)

    server.run_stdio()


if __name__ == "__main__":
    main()
