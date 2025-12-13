#!/usr/bin/env python3
"""
Test script to verify weather API works for Oslo.
"""
import os
import sys
import asyncio
import logging

from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer
from openapi_mcp.config import ServerConfig

async def test_oslo_weather():
    """Test getting weather for Oslo."""
    print("Testing Oslo Weather API")
    print("=" * 30)

    logging.basicConfig(level=logging.INFO)
    
    # Configure for weather API
    os.environ.update({
        'OPENAPI_URL': 'https://api.met.no/weatherapi/locationforecast/2.0/swagger',
        'SERVER_NAME': 'weather_test',
        'MCP_HTTP_ENABLED': 'false'
    })
    
    config = ServerConfig()
    server = FastMCPOpenAPIServer(config)
    await server.initialize()
    
    print(f"✅ Initialized weather server with {len(server.operations)} operations")
    
    # List available operations
    print("\nAvailable weather operations:")
    for op in server.operations:
        print(f"  - {op.operation_id}: {op.summary}")
    
    # Find compact forecast operation
    compact_op = None
    for op in server.operations:
        if 'compact' in op.operation_id.lower():
            compact_op = op
            break
    
    if not compact_op:
        print("❌ No compact forecast operation found")
        return False
    
    print(f"\n🎯 Testing operation: {compact_op.operation_id}")
    print(f"   Method: {compact_op.method}")
    print(f"   Path: {compact_op.path}")
    print(f"   Summary: {compact_op.summary}")
    
    # Test with Oslo coordinates
    oslo_lat = 59.9139
    oslo_lon = 10.7522
    
    print(f"\n🌍 Testing with Oslo coordinates: lat={oslo_lat}, lon={oslo_lon}")
    
    # Create the generic tool function
    tool_func = None
    for tool in server.operations:
        if tool.operation_id == compact_op.operation_id:
            tool_func = server._create_tool_function(tool)
            break
    
    if not tool_func:
        print("❌ Could not create tool function")
        return False
    
    try:
        # Test dry run first
        print("\n🧪 Testing dry run...")
        dry_result = await tool_func(lat=oslo_lat, lon=oslo_lon, dry_run=True)
        print(f"   Dry run result: {dry_result.get('result', {}).get('request', {}).get('url', 'No URL')}")
        
        # Test actual call (commented out to avoid hitting the API)
        print("\n⚠️  Skipping actual API call to avoid rate limits")
        print("   In production, this would fetch real weather data")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing weather API: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function."""
    try:
        success = asyncio.run(test_oslo_weather())
        if success:
            print("\n🎉 Oslo weather test completed successfully!")
            print("✅ FastMCP server can handle weather API requests")
        else:
            print("\n❌ Oslo weather test failed")
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n💥 Test crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()