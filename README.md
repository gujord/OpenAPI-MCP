# OpenAPI to Model Context Protocol (MCP)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Repo Size](https://img.shields.io/github/repo-size/gujord/OpenAPI-MCP)
![Last Commit](https://img.shields.io/github/last-commit/gujord/OpenAPI-MCP)
![Open Issues](https://img.shields.io/github/issues/gujord/OpenAPI-MCP)

![OpenAPI-MCP](OpenAPI-MCP.png)

The OpenAPI to Model Context Protocol (MCP) proxy server bridges the gap between AI agents and external APIs by dynamically translating OpenAPI specifications into standardized MCP tools. This simplifies the integration process, significantly reducing development time and complexity associated with custom API wrappers.

- **Repository:** [https://github.com/gujord/OpenAPI-MCP](https://github.com/gujord/OpenAPI-MCP)

---

## Why MCP?

The Model Context Protocol (MCP), developed by Anthropic, standardizes communication between Large Language Models (LLMs) and external data sources or tools. By acting as a universal interface (like a USB-C port for AI), MCP enables AI agents to interact with diverse APIs seamlessly, without bespoke integration code.

## Key Features

- **Dynamic Tool Generation:** Automatically registers OpenAPI endpoints as MCP tools.
- **Multiple Transport Methods:** Supports both `stdio` and Server-Sent Events (`sse`).
- **OAuth2 Support:** Secure machine-to-machine interactions with OAuth2 Client Credentials.
- **Dry Run Mode:** Safely simulate API interactions before live execution.
- **JSON-RPC 2.0 Compliance:** Robust and clear communication with added `server_name` context.
- **AI Orchestrator Integration:** Compatible with Cursor, Windsurf, Claude Desktop, and other popular tools.

---

## Quick Start

### Installation
```bash
git clone https://github.com/gujord/OpenAPI-MCP.git
cd OpenAPI-MCP
pip install -r requirements.txt
```

### Environment Configuration

| Variable              | Description                          | Required | Default                |
|-----------------------|--------------------------------------|----------|------------------------|
| `OPENAPI_URL`         | URL of the OpenAPI specification     | Yes      | -                      |
| `TRANSPORT`           | Communication method (`stdio`, `sse`)| No       | `stdio`                |
| `SERVER_NAME`         | Custom server identifier             | No       | `openapi_proxy_server` |
| `OAUTH_CLIENT_ID`     | OAuth Client ID                      | No       | -                      |
| `OAUTH_CLIENT_SECRET` | OAuth Client Secret                  | No       | -                      |
| `OAUTH_TOKEN_URL`     | OAuth Token URL                      | No       | -                      |
| `OAUTH_SCOPE`         | OAuth Scope                          | No       | `api`                  |

### Running the Server
```bash
# Default (stdio mode)
python src/openapi-mcp.py

# Custom environment
OPENAPI_URL=https://api.example.com/openapi.json python src/openapi-mcp.py

# SSE mode
TRANSPORT=sse python src/openapi-mcp.py
```

---

## How It Works

1. **Load Specification:** Parses the OpenAPI specification.
2. **Generate Tools:** Converts endpoints into MCP-compatible tools.
3. **Validate Parameters:** Ensures API call accuracy.
4. **Handle Authentication:** Manages OAuth tokens securely.
5. **Execute Requests:** Performs HTTP requests securely via `httpx`.
6. **Format Response:** Delivers results using JSON-RPC 2.0.

---

## JSON-RPC API (SSE Mode)

- **`POST /jsonrpc`**: Handles JSON-RPC requests.
- **`GET /sse`**: Streams JSON-RPC responses and tool metadata.

### Example Request
```json
{
  "jsonrpc": "2.0",
  "method": "get_users",
  "params": {"limit": 10, "page": 1},
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
    "users": [{"id": 1, "name": "User 1"}],
    "total": 1
  }
}
```

---

## LLM Orchestrator Configuration

### Cursor (`~/.cursor/mcp.json`)
```json
{
  "mcpServers": {
    "barentswatch": {
      "command": "PATH-TO-OPENAPI-MCP/venv/bin/python",
      "args": ["PATH-TO-OPENAPI-MCP/src/openapi-mcp.py", "server"],
      "env": {"OPENAPI_URL": "https://live.ais.barentswatch.no/live/openapi/ais/openapi.json"}
    }
  }
}
```

### Windsurf (`~/.codeium/windsurf/mcp_config.json`)
```json
{
  "mcpServers": {
    "locationforecast": {
      "command": "bash",
      "args": ["-c", "source PATH-TO-OPENAPI-MCP/venv/bin/activate && python3 PATH-TO-OPENAPI-MCP/src/openapi-mcp.py server"],
      "env": {"OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger"}
    }
  }
}
```

---

## Contributing

- Fork and clone
- Create a branch
- Submit a pull request

---

## License

[MIT License](LICENSE)

---

This project leverages the concept of "Vibe Coding," harnessing powerful Large Language Models (LLMs) such as Gemini, OpenAI's o3-mini-high, and Claude 3.7, significantly accelerating development and prototyping.

If this tool aids your AI agent development, please give it a ⭐ on GitHub!

