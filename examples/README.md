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

### demo_xquik_openapi.py

Shows how to expose Xquik's public OpenAPI specification as MCP tools with a
bearer-token header.

```bash
# Run from project root
XQUIK_API_KEY=your-key python examples/demo_xquik_openapi.py
```

This example:
- Loads `https://xquik.com/openapi.json`
- Passes `Authorization: Bearer ...` through `MCP_AUTH_HEADERS`
- Prints a Claude Desktop stdio configuration using `XQUIK_API_KEY`

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
