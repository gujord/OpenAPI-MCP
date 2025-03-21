# OpenAPI to Model Context Protocol (MCP)

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Repo Size](https://img.shields.io/github/repo-size/gujord/OpenAPI-MCP)
![Last Commit](https://img.shields.io/github/last-commit/gujord/OpenAPI-MCP)
![Open Issues](https://img.shields.io/github/issues/gujord/OpenAPI-MCP)

![OpenAPI-MCP](OpenAPI-MCP.png)

A flexible proxy server that converts OpenAPI specifications into MCP (Model Context Protocol) tools, enabling Large Language Models (LLMs) to interact with any API that publishes an OpenAPI/Swagger specification.

Official repository: [https://github.com/gujord/OpenAPI-MCP](https://github.com/gujord/OpenAPI-MCP)

---

## Features

- **Dynamic Tool Generation**: Automatically loads OpenAPI/Swagger specifications and dynamically registers endpoints as callable MCP tools  
- **Multiple Transport Options**: Supports both stdio and Server-Sent Events (SSE) transport methods  
- **OAuth Support**: Built-in OAuth client credentials flow support with error handling  
- **Dry Run Mode**: Simulate API calls without making actual requests (`dry_run=True`)  
- **JSON-RPC Compliance**: Full JSON-RPC 2.0 protocol support with a top-level `server_name` field  
- **LLM Integration**: Seamless integration with orchestrators like Cursor, Windsurf, and Claude Desktop  

---

## Installation

```bash
git clone https://github.com/gujord/OpenAPI-MCP.git
cd OpenAPI-MCP
pip install -r requirements.txt
```

---

## Usage

### Environment Variables

| Variable              | Description                                  | Required | Default                |
|-----------------------|----------------------------------------------|----------|------------------------|
| `OPENAPI_URL`         | URL to the OpenAPI specification             | Yes      | -                      |
| `TRANSPORT`           | Transport method (`stdio` or `sse`)          | No       | `stdio`                |
| `SERVER_NAME`         | Custom name for the server                   | No       | `openapi_proxy_server` |
| `OAUTH_CLIENT_ID`     | OAuth client ID                              | No       | -                      |
| `OAUTH_CLIENT_SECRET` | OAuth client secret                          | No       | -                      |
| `OAUTH_TOKEN_URL`     | OAuth token endpoint URL                     | No       | -                      |
| `OAUTH_SCOPE`         | OAuth scope                                  | No       | `api`                  |

### Running the Server

```bash
# Default (stdio mode)
python src/openapi-mcp.py

# With custom environment
OPENAPI_URL=https://api.example.com/openapi.json python src/openapi-mcp.py

# SSE mode
TRANSPORT=sse python src/openapi-mcp.py
```

---

## How It Works

1. **Specification Loading**: Loads OpenAPI/Swagger spec from the given URL  
2. **Tool Generation**: Creates MCP tool functions from each API operation  
3. **Parameter Validation**: Validates required input parameters  
4. **Authentication**: Retrieves OAuth access tokens if credentials are provided  
    - If OAuth token retrieval fails, the server exits with code `1`  
5. **Request Execution**: Performs real HTTP requests via `httpx`  
6. **Response Formatting**: Returns results as JSON-RPC 2.0 with `server_name`  

---

## JSON-RPC API (SSE Mode)

- **POST /jsonrpc**: Accepts JSON-RPC 2.0 requests  
- **GET /sse**: Streams JSON-RPC responses to clients  

Upon connection to `/sse`, a metadata response containing available tools is emitted automatically using `tools_list` with `id: 1`.

### Example Request

```json
{
  "jsonrpc": "2.0",
  "method": "get_users",
  "params": {
    "limit": 10,
    "page": 1
  },
  "id": 1
}
```

### Example Response

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "server_name": "openapi_proxy_server",
  "result": {
    "users": [
      {"id": 1, "name": "User 1"},
      {"id": 2, "name": "User 2"}
    ],
    "total": 2
  }
}
```

---

## LLM Orchestrator Configuration

Supports both Cursor and Windsurf via MCP JSON config:

```json
{
    "mcpServers": {
        "barentswatch": {
            "command": "bash",
            "args": [
                "-c",
                "source PATH-TO-OPENAPI-MCP/venv/bin/activate && python3 PATH-TO-OPENAPI-MCP/src/openapi-mcp.py server"
            ],
            "env": {
                "OPENAPI_URL": "https://live.ais.barentswatch.no/live/openapi/ais/openapi.json"
            }
        },
        "locationforecast": {
            "command": "bash",
            "args": [
                "-c",
                "source PATH-TO-OPENAPI-MCP/venv/bin/activate && python3 PATH-TO-OPENAPI-MCP/src/openapi-mcp.py server"
            ],
            "env": {
                "OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger"
            }
        }
    }
}
```

---

## Development

### Contribute

- Fork the repo  
- Create a branch  
- Submit a pull request  

---

## License

MIT License – see [LICENSE](LICENSE)

---

If you like the direction of this project, consider giving it a ⭐ on GitHub!