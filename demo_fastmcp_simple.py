#!/usr/bin/env python3
"""
Simple demo of the FastMCP OpenAPI server.
Shows how to run the server with stdio transport.
"""
import os
import sys
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def main():
    """Main demo function."""
    from fastmcp_server import FastMCPOpenAPIServer
    from config import ServerConfig
    
    # Configure for Norwegian Weather API (no auth required)
    os.environ.update({
        'OPENAPI_URL': 'https://api.met.no/weatherapi/locationforecast/2.0/swagger',
        'SERVER_NAME': 'weather_fastmcp',
        'MCP_HTTP_ENABLED': 'false'  # Use stdio transport
    })
    
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
    print(f"""
{{
  "mcpServers": {{
    "weather": {{
      "command": "{sys.executable}",
      "args": ["{os.path.abspath(__file__)}"],
      "transport": "stdio"
    }}
  }}
}}
""")
    
    # For demo, just show what tools are available
    tools = await server.mcp.get_tools()
    print(f"\nAvailable tools ({len(tools)}):")
    tools_list = list(tools.values()) if isinstance(tools, dict) else list(tools)
    for tool in tools_list[:10]:  # Show first 10
        print(f"  - {tool.name}")
    
    if len(tools_list) > 10:
        print(f"  ... and {len(tools_list) - 10} more tools")
    
    print("\nStarting stdio server...")
    # This will run the server with stdio transport
    server.run_stdio()

if __name__ == "__main__":
    asyncio.run(main())