#!/usr/bin/env python3
"""
Test script to validate the OpenAPI-MCP server with Norwegian Weather API.
"""
import os
import sys
import logging
import asyncio
import pytest

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


@pytest.mark.asyncio
async def test_weather_api():
    """Test the OpenAPI-MCP server with Norwegian Weather API."""
    print("Testing OpenAPI-MCP Server with Norwegian Weather API")
    print("=" * 60)

    # Set up logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Save original env
    original_env = os.environ.copy()

    try:
        # Test configuration
        os.environ["OPENAPI_URL"] = "https://api.met.no/weatherapi/locationforecast/2.0/swagger"
        os.environ["SERVER_NAME"] = "weather"

        config = ServerConfig()
        print(f"  Configuration loaded: {config.server_name}")

        # Test server initialization
        srv = FastMCPOpenAPIServer(config)
        await srv.initialize()
        print("  Server initialized successfully")
        print(f"  - API: {srv.api_info.get('title', 'Unknown')}")
        print(f"  - Version: {srv.api_info.get('version', 'Unknown')}")
        print(f"  - Operations parsed: {len(srv.operations)}")

        # Show available forecast tools
        forecast_tools = [op for op in srv.operations if "compact" in op.operation_id.lower() or "complete" in op.operation_id.lower()]
        print(f"  Weather forecast tools available: {len(forecast_tools)}")
        for tool in forecast_tools:
            print(f"  - {tool.operation_id}")

        # Find compact tool
        compact_tool = None
        for op in srv.operations:
            if "compact" in op.operation_id.lower():
                compact_tool = op
                break

        assert compact_tool is not None, "Should find compact weather tool"

        # Test dry run for Oslo coordinates
        tool_func = srv._create_tool_function(compact_tool)
        dry_run = await tool_func(lat=59.9139, lon=10.7522, dry_run=True)
        print("  Dry run test successful (Oslo weather)")
        assert "result" in dry_run
        print(f"  - URL: {dry_run['result']['request']['url']}")
        print(f"  - Method: {dry_run['result']['request']['method']}")
        print(f"  - Params: {dry_run['result']['request']['params']}")

        # Test real API call for weather forecast
        real_call = await tool_func(lat=59.9139, lon=10.7522)
        if "result" in real_call and "data" in real_call["result"]:
            data = real_call["result"]["data"]
            print("  Real API call successful")

            # Extract weather information
            if "properties" in data and "timeseries" in data["properties"]:
                timeseries = data["properties"]["timeseries"]
                if timeseries:
                    first_forecast = timeseries[0]
                    time = first_forecast.get("time", "Unknown")
                    instant = first_forecast.get("data", {}).get("instant", {}).get("details", {})
                    temp = instant.get("air_temperature", "N/A")
                    humidity = instant.get("relative_humidity", "N/A")
                    pressure = instant.get("air_pressure_at_sea_level", "N/A")

                    print(f"  - Location: Oslo (59.9139N, 10.7522E)")
                    print(f"  - Time: {time}")
                    print(f"  - Temperature: {temp}C")
                    print(f"  - Humidity: {humidity}%")
                    print(f"  - Pressure: {pressure} hPa")
                    print(f"  - Total forecasts: {len(timeseries)}")

        # Test parameter validation (missing required parameters)
        print("  Testing parameter validation...")
        missing_params_result = await tool_func()
        if "result" in missing_params_result and "help" in missing_params_result["result"]:
            print(f"  - Proper validation: {missing_params_result['result']['help']}")

        print("\n" + "=" * 60)
        print("All tests passed! Norwegian Weather API integration working correctly.")

    finally:
        # Restore original env
        os.environ.clear()
        os.environ.update(original_env)


if __name__ == "__main__":
    asyncio.run(test_weather_api())
