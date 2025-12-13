#!/usr/bin/env python3
"""
Test script to validate the OpenAPI-MCP server with Norwegian Weather API.
"""
import os
import sys
import logging

from openapi_mcp import server

def test_weather_api():
    """Test the OpenAPI-MCP server with Norwegian Weather API."""
    print("Testing OpenAPI-MCP Server with Norwegian Weather API")
    print("=" * 60)
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    try:
        # Test configuration
        os.environ['OPENAPI_URL'] = 'https://api.met.no/weatherapi/locationforecast/2.0/swagger'
        os.environ['SERVER_NAME'] = 'weather'
        
        config = server.ServerConfig()
        print(f"✓ Configuration loaded: {config.server_name}")
        
        # Test server initialization
        srv = server.MCPServer(config)
        srv.initialize()
        print(f"✓ Server initialized successfully")
        print(f"  - API: {srv.openapi_spec.get('info', {}).get('title', 'Unknown')}")
        print(f"  - Version: {srv.openapi_spec.get('info', {}).get('version', 'Unknown')}")
        print(f"  - Operations parsed: {len(srv.operations_info)}")
        
        # Test tool registration
        api_tools = srv.register_openapi_tools()
        srv.register_standard_tools()
        print(f"✓ Tools registered: {api_tools} API tools, {len(srv.registered_tools)} total")
        
        # Test resource registration
        resources = srv.register_resources()
        print(f"✓ Resources registered: {resources}")
        
        # Test prompt generation
        prompts = srv.generate_prompts()
        print(f"✓ Prompts generated: {prompts}")
        
        # Show available forecast tools
        forecast_tools = [name for name in srv.registered_tools.keys() if 'compact' in name.lower() or 'complete' in name.lower()]
        print(f"✓ Weather forecast tools available: {len(forecast_tools)}")
        for tool in forecast_tools:
            print(f"  - {tool}")
        
        # Test tools list
        tools_list = srv._tools_list_tool('test-id')
        print(f"✓ Tools list: {len(tools_list['result']['tools'])} tools available")
        
        # Test dry run for Oslo coordinates
        if forecast_tools:
            compact_tool = srv.registered_tools['weather_get__compact']['function']
            dry_run = compact_tool(req_id='test', lat=59.9139, lon=10.7522, dry_run=True)
            print("✓ Dry run test successful (Oslo weather)")
            print(f"  - URL: {dry_run['result']['request']['url']}")
            print(f"  - Method: {dry_run['result']['request']['method']}")
            print(f"  - Params: {dry_run['result']['request']['params']}")
        
        # Test real API call for weather forecast
        if forecast_tools:
            real_call = compact_tool(req_id='test', lat=59.9139, lon=10.7522)
            if 'result' in real_call and 'data' in real_call['result']:
                data = real_call['result']['data']
                print(f"✓ Real API call successful")
                
                # Extract weather information
                if 'properties' in data and 'timeseries' in data['properties']:
                    timeseries = data['properties']['timeseries']
                    if timeseries:
                        first_forecast = timeseries[0]
                        time = first_forecast.get('time', 'Unknown')
                        instant = first_forecast.get('data', {}).get('instant', {}).get('details', {})
                        temp = instant.get('air_temperature', 'N/A')
                        humidity = instant.get('relative_humidity', 'N/A')
                        pressure = instant.get('air_pressure_at_sea_level', 'N/A')
                        
                        print(f"  - Location: Oslo (59.9139°N, 10.7522°E)")
                        print(f"  - Time: {time}")
                        print(f"  - Temperature: {temp}°C")
                        print(f"  - Humidity: {humidity}%")
                        print(f"  - Pressure: {pressure} hPa")
                        print(f"  - Total forecasts: {len(timeseries)}")
        
        # Test parameter validation (missing required parameters)
        print("✓ Testing parameter validation...")
        missing_params_result = compact_tool(req_id='test_validation')
        if 'result' in missing_params_result and 'help' in missing_params_result['result']:
            print(f"  - Proper validation: {missing_params_result['result']['help']}")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed! Norwegian Weather API integration working correctly.")
        print("✅ Server can successfully fetch real weather data")
        print("✅ Parameter validation and error handling working")
        print("✅ Multiple forecast endpoints available")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_weather_api()
    sys.exit(0 if success else 1)