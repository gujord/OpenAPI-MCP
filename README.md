# OpenAPI to Model Context Protocol (MCP)

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Repo Size](https://img.shields.io/github/repo-size/gujord/OpenAPI-MCP)
![Last Commit](https://img.shields.io/github/last-commit/gujord/OpenAPI-MCP)
![Open Issues](https://img.shields.io/github/issues/gujord/OpenAPI-MCP)

OpenAPI-MCP makes any API available to Large Language Models (LLMs) through the Model Context Protocol (MCP). It automatically loads OpenAPI/Swagger specifications and dynamically registers endpoints as callable MCP tools. The MCP server responds in JSON-RPC 2.0 format and includes a top-level `server_name` field, making it straightforward for orchestrators like Cursor, Windsurf, and Claude Desktop to discover and invoke API endpoints.

**Note:** This project is still in development and may have limitations or bugs. Use with caution.

If you like the direction of this project, consider giving it a ⭐ on GitHub!

![OpenAPI-MCP](OpenAPI-MCP.png)

## Features

- **Dynamic Endpoint Generation:** Automatically extracts API endpoint details from OpenAPI specifications (JSON/YAML) and registers them as MCP tools.
- **JSON-RPC 2.0 Compliance:** All responses follow the JSON-RPC 2.0 standard with a top-level `server_name` field.
- **Error Handling & Help Documentation:** Provides detailed messages for missing parameters, unknown endpoints, or API errors.
- **Authentication Support:** Supports both direct access tokens and OAuth client_credentials authentication.
- **LLM Integration via MCP:** Endpoints are exposed as tools that LLMs can invoke. The generic MCP server output is compatible with integrations like Cursor, Windsurf, and Claude Desktop.
- **Experimental SSE Support:** An experimental SSE implementation attempts to stream JSON-RPC responses (including a welcome notification with the tools list) to clients. **Note:** This SSE implementation is still a work in progress and has not been fully verified with Cursor.

## Prerequisites

- Python 3.7 or newer
- Virtual environment recommended
- Dependencies listed in `requirements.txt`

## Setup Instructions

1. **Create a Virtual Environment:**

   ```bash
   python3 -m venv venv
   ```

2. **Activate the Virtual Environment:**

   - **Linux/macOS:**

     ```bash
     source venv/bin/activate
     ```

   - **Windows:**

     ```bash
     venv\Scripts\activate
     ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables

Set the necessary environment variables before running the MCP server:

### OpenAPI Specification

- **OPENAPI_URL**: URL pointing to your OpenAPI specification (JSON or YAML).

  ```bash
  export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger"
  ```

### OAuth Authentication (Optional)

If using OAuth client_credentials authentication, set:

- **OAUTH_CLIENT_ID**
- **OAUTH_CLIENT_SECRET**
- **OAUTH_SCOPE** (default: `api`)
- **OAUTH_TOKEN_URL**

For direct access tokens, set:

- **AUTH_TOKEN**

## Model Context Protocol (MCP) Configuration

The MCP integration now returns JSON-RPC 2.0 responses including a top-level `server_name` field. Endpoints are dynamically registered as MCP tools. Note that tool names must only contain alphanumeric characters, underscores, or hyphens. For example, the metadata tool is registered as `tools_list` (underscore instead of a forward slash).

## Experimental SSE Support

An experimental SSE (Server-Sent Events) implementation is provided. When running in SSE mode, the server:

- Exposes a `/jsonrpc` endpoint to receive JSON-RPC requests.
- Exposes a `/sse` endpoint that streams JSON-RPC responses and immediately sends a welcome notification containing the tools list.

**Important:** This SSE implementation is still under development and has not been fully verified with Cursor. If you experience issues with tool discovery or streaming responses in Cursor, please be aware that this feature is experimental.

## Example MCP Config for Cursor

Create a file called `.cursor/mcp.json` in your project root (or in your home directory for a global configuration) with the following content:

```json
{
  "mcpServers": {
    "barentswatch": {
      "command": "bash",
      "args": [
        "-c",
        "source /path/to/venv/bin/activate && python3 /path/to/openapi-mcp.py --server barentswatch --openapi-url 'https://live.ais.barentswatch.no/live/openapi/ais/openapi.json' api tools_list"
      ],
      "env": {
        "OPENAPI_URL": "https://live.ais.barentswatch.no/live/openapi/ais/openapi.json"
      }
    }
  }
}
```

Cursor will read this configuration, launch the MCP server using the specified command, and then discover the exposed tools (remember that Cursor supports up to 40 tools). When interacting with the Cursor agent, reference the tool names or descriptions as provided by the MCP server.

## Example MCP Config for Windsurf

For Windsurf, create a JSON config (typically in `~/.codeium/windsurf/mcp_config.json`) with a similar structure:

```json
{
    "mcpServers": {
        "barentswatch": {
            "command": "bash",
            "args": [
                "-c",
                "source /path/to/venv/bin/activate && python3 /path/to/openapi-mcp.py --server barentswatch --openapi-url 'https://live.ais.barentswatch.no/live/openapi/ais/openapi.json'"
            ],
            "env": {
                "OPENAPI_URL": "https://live.ais.barentswatch.no/live/openapi/ais/openapi.json"
            }
        },
        "locationforecast": {
            "command": "bash",
            "args": [
                "-c",
                "source /path/to/venv/bin/activate && python3 /path/to/openapi-mcp.py --server locationforecast --openapi-url 'https://api.met.no/weatherapi/locationforecast/2.0/swagger'"
            ],
            "env": {
                "OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger"
            }
        }
    }
}
```

Note: Windsurf supports only MCP tools, and each tool invocation may consume credits.

## Usage

### Standard (Stdio) Mode

List endpoints from the OpenAPI specification. The response is a JSON-RPC 2.0 message including a top-level `server_name` field. Use the updated tool name `tools_list`:

```bash
python3 src/openapi-mcp.py api tools_list --output json
```

Example with a different API (YAML output example):

```bash
export OPENAPI_URL="https://nvdbapiles.atlas.vegvesen.no/openapi.yaml"
python3 src/openapi-mcp.py api tools_list --output yaml
```

### Calling an Endpoint

Invoke an endpoint with parameters. The response will be a JSON-RPC 2.0 message with a top-level `server_name`:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10
```

To simulate a call without sending a real API request, use the dry-run mode:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10 --dry-run
```

### Experimental SSE Mode

To start the server in SSE mode, set the `TRANSPORT` environment variable to `sse` and run the server. This will launch the FastAPI app with `/jsonrpc` and `/sse` endpoints. The `/sse` endpoint streams a welcome notification (including the tools list) and subsequent JSON-RPC responses.

```bash
export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger" TRANSPORT=sse && python3 src/openapi-mcp.py
```

When you visit [http://127.0.0.1:8000/sse](http://127.0.0.1:8000/sse) in your browser (or when Cursor connects), you should see a JSON-RPC notification containing a welcome message and a list of available tools. **Note:** This SSE support is experimental and still under development.

## Integration with LLMs via MCP

OpenAPI-MCP is designed to integrate seamlessly with MCP orchestrators:

- **Dynamic Registration:** Endpoints from the OpenAPI spec are automatically registered as MCP tools.
- **LLM Invocation:** LLMs invoke endpoints using the registered operation IDs. All responses conform to JSON-RPC 2.0, making them easily interpretable by the orchestrator.
- **Generic Server:** The server is language-agnostic and works with various clients (Cursor, Windsurf, Claude Desktop) without additional modification.
- **Experimental SSE Support:** The server attempts to provide SSE streaming of JSON-RPC messages. This feature is experimental and subject to further verification and improvement.

## Troubleshooting

- **OPENAPI_URL:** Ensure the URL is accessible and the specification is correctly formatted (JSON or YAML).
- **OAuth Errors:** Double-check that all necessary OAuth environment variables are set.
- **Parameter Issues:** Use the `--dry-run` flag to validate parameters and check for missing or incorrectly formatted values.
- **Tool Naming:** Tool names must only contain alphanumeric characters, underscores, or hyphens. If you encounter errors related to tool names, verify that you are not using invalid characters (e.g., forward slashes).
- **SSE Mode:** SSE support is experimental. If tools are not discovered correctly via SSE, try using the standard (stdio) mode or consult the issue tracker.

## Contributions

Contributions are welcome. Please open an issue or submit a pull request if you have improvements or bug fixes.

If you like this project, consider giving it a ⭐ on GitHub!

## License & Credits

This project is licensed under the [MIT License](LICENSE). For API-specific client registration details, refer to the respective API provider's documentation.
