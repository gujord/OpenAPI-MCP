# OpenAPI-MCP Examples

This directory contains example scripts demonstrating how to use the OpenAPI-MCP server.

## Examples

### demo_fastmcp_simple.py

A simple demo showing how to run the FastMCP OpenAPI server with stdio transport.

```bash
# Run from project root
python examples/demo_fastmcp_simple.py
```

This example:
- Connects to the Norwegian Weather API
- Registers all API operations as MCP tools
- Shows how to configure for Claude Desktop integration

### demo_sse.py

Demonstrates Server-Sent Events (SSE) transport functionality.

```bash
# Run from project root
python examples/demo_sse.py
```

This example:
- Starts an SSE server on http://127.0.0.1:8003
- Connects to the Petstore API
- Shows real-time streaming capabilities

### demo_xquik_api_key.py

Shows how to load a hosted OpenAPI document for an API that expects a custom
header API key on upstream requests.

```bash
export XQUIK_API_KEY="your-api-key"
python examples/demo_xquik_api_key.py
```

This example:
- Connects to Xquik's hosted OpenAPI 3.1 document
- Configures the `x-api-key` header through `MCP_AUTH_HEADERS`
- Keeps the API key in the environment and never prints it
- Exposes X search, monitoring, extraction, and write operations as MCP tools
- Keeps status messages on stderr so stdio MCP messages remain valid

Create an API key with the [Xquik quickstart](https://docs.xquik.com/quickstart).
The live schema is available at <https://xquik.com/openapi.json>.

Xquik is an independent third-party service. Not affiliated with X Corp.
"Twitter" and "X" are trademarks of X Corp.

## Running Examples

Before running examples, ensure you have the package installed:

```bash
# Install in development mode
pip install -e .

# Or install from PyPI
pip install openapi-mcp-proxy
```

## Environment Variables

All examples can be customized via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAPI_URL` | URL to OpenAPI specification | Required |
| `SERVER_NAME` | Name of the MCP server | `openapi_proxy_server` |
| `MCP_HTTP_ENABLED` | Enable HTTP/SSE transport | `false` |
| `MCP_HTTP_HOST` | HTTP server host | `127.0.0.1` |
| `MCP_HTTP_PORT` | HTTP server port | `8000` |

See the main README for the full list of configuration options.
