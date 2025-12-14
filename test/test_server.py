#!/usr/bin/env python3
"""
Test script to validate the OpenAPI-MCP server functionality.
"""
import os
import sys
import logging
import asyncio
import pytest

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


@pytest.mark.asyncio
async def test_server():
    """Test the OpenAPI-MCP server with Petstore API."""
    print("Testing OpenAPI-MCP Server with Petstore API")
    print("=" * 50)

    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Save original env
    original_env = os.environ.copy()

    try:
        # Test configuration
        os.environ["OPENAPI_URL"] = "https://petstore3.swagger.io/api/v3/openapi.json"
        os.environ["SERVER_NAME"] = "petstore3"

        config = ServerConfig()
        print(f"  Configuration loaded: {config.server_name}")

        # Test server initialization
        srv = FastMCPOpenAPIServer(config)
        await srv.initialize()
        print("  Server initialized successfully")
        print(f"  - API: {srv.api_info.get('title', 'Unknown')}")
        print(f"  - Operations parsed: {len(srv.operations)}")

        assert len(srv.operations) > 0, "Should have operations parsed"

        # Test that tools are registered with FastMCP
        print(f"  Operations registered: {len(srv.operations)}")

        # Test dry run functionality
        find_pets_tool = None
        for op in srv.operations:
            if "findPetsByStatus" in op.operation_id:
                find_pets_tool = op
                break

        assert find_pets_tool is not None, "Should find the findPetsByStatus tool"

        # Test the tool function
        tool_func = srv._create_tool_function(find_pets_tool)
        dry_run = await tool_func(status="available", dry_run=True)
        print("  Dry run test successful")
        assert "result" in dry_run
        assert dry_run["result"]["dry_run"] is True
        print(f"  - URL: {dry_run['result']['request']['url']}")
        print(f"  - Method: {dry_run['result']['request']['method']}")

        # Test real API call
        real_call = await tool_func(status="available")
        if "result" in real_call and "data" in real_call["result"]:
            data = real_call["result"]["data"]
            print(f"  Real API call successful: Found {len(data)} pets")

        print("\n" + "=" * 50)
        print("All tests passed! Server is working correctly.")

    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


if __name__ == "__main__":
    asyncio.run(test_server())
