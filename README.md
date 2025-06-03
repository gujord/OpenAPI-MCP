# OpenAPI to Model Context Protocol (MCP)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Repo Size](https://img.shields.io/github/repo-size/gujord/OpenAPI-MCP)
![Last Commit](https://img.shields.io/github/last-commit/gujord/OpenAPI-MCP)
![Open Issues](https://img.shields.io/github/issues/gujord/OpenAPI-MCP)
![Python version](https://img.shields.io/badge/Python-3.12-blue)

**The OpenAPI-MCP proxy translates OpenAPI specs into MCP tools, enabling AI agents to access external APIs without custom wrappers!**

![OpenAPI-MCP](https://raw.githubusercontent.com/gujord/OpenAPI-MCP/main/img/Open-API-MCP-relations.png)

## Bridge the gap between AI agents and external APIs

The OpenAPI to Model Context Protocol (MCP) proxy server bridges the gap between AI agents and external APIs by **dynamically translating** OpenAPI specifications into standardized **MCP tools**, **resources**, and **prompts**. This simplifies integration by eliminating the need for custom API wrappers.

Built with **FastMCP** following official MCP patterns and best practices, the server provides:
- ✅ **Official FastMCP Integration** - Uses the latest FastMCP framework for optimal performance
- ✅ **Proper MCP Transport** - Supports stdio, SSE, and streamable HTTP transports
- ✅ **Modular Architecture** - Clean separation of concerns with dependency injection
- ✅ **Production Ready** - Robust error handling, comprehensive logging, and type safety

- **Repository:** [https://github.com/gujord/OpenAPI-MCP](https://github.com/gujord/OpenAPI-MCP)

---

If you find it useful, please give it a ⭐ on GitHub!

---

## Key Features

### Core Functionality
- **FastMCP Transport:** Optimized for `stdio`, working out-of-the-box with popular LLM orchestrators.
- **OpenAPI Integration:** Parses and registers OpenAPI operations as callable tools.
- **Resource Registration:** Automatically converts OpenAPI component schemas into resource objects with defined URIs.
- **Prompt Generation:** Generates contextual prompts based on API operations to guide LLMs in using the API.
- **Dual Authentication:** Supports both OAuth2 Client Credentials flow and username/password authentication with automatic token caching.
- **MCP HTTP Transport:** Official MCP-compliant HTTP streaming transport with JSON-RPC 2.0 over SSE.
- **Server-Sent Events (SSE):** Legacy streaming support (deprecated - use MCP HTTP transport).
- **JSON-RPC 2.0 Support:** Fully compliant request/response structure.

### Advanced Features
- **Modular Architecture:** Clean separation of concerns with dedicated modules for authentication, request handling, and tool generation.
- **Robust Error Handling:** Comprehensive exception hierarchy with proper JSON-RPC error codes and structured error responses.
- **Auto Metadata:** Derives tool names, summaries, and schemas from the OpenAPI specification.
- **Sanitized Tool Names:** Ensures compatibility with MCP name constraints.
- **Flexible Parameter Parsing:** Supports query strings, JSON, and comma-separated formats with intelligent type conversion.
- **Enhanced Parameter Handling:** Automatically converts parameters to correct data types with validation.
- **Extended Tool Metadata:** Includes detailed parameter information, response schemas, and API categorization.
- **CRUD Operation Detection:** Automatically identifies and generates example prompts for Create, Read, Update, Delete operations.
- **MCP-Compliant Streaming:** Official MCP HTTP transport for real-time streaming with proper session management.

### Developer Experience
- **Configuration Management:** Centralized environment variable handling with validation and defaults.
- **Comprehensive Logging:** Structured logging with appropriate levels for debugging and monitoring.
- **Type Safety:** Full type hints and validation throughout the codebase.
- **Extensible Design:** Factory patterns and dependency injection for easy customization and testing.

## Quick Start

### Installation

```bash
git clone https://github.com/gujord/OpenAPI-MCP.git
cd OpenAPI-MCP
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### FastMCP Usage (Recommended)

The server now uses FastMCP for optimal MCP compliance and performance:

```bash
# Run with stdio transport (for Claude Desktop/Cursor/Windsurf)
OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger" \
SERVER_NAME="weather" \
python src/fastmcp_server.py

# Run with SSE transport (for web clients)
OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger" \
SERVER_NAME="weather" \
MCP_HTTP_ENABLED="true" \
MCP_HTTP_PORT="8001" \
python src/fastmcp_server.py
```

### Multiple API Servers

To run multiple OpenAPI services simultaneously, start each server on different ports:

```bash
# Terminal 1: Weather API
source venv/bin/activate && \
OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger" \
SERVER_NAME="weather" \
MCP_HTTP_ENABLED="true" \
MCP_HTTP_PORT="8001" \
python src/fastmcp_server.py

# Terminal 2: Petstore API  
source venv/bin/activate && \
OPENAPI_URL="https://petstore3.swagger.io/api/v3/openapi.json" \
SERVER_NAME="petstore" \
MCP_HTTP_ENABLED="true" \
MCP_HTTP_PORT="8002" \
python src/fastmcp_server.py
```

### Docker Compose (Multiple Services)

For production deployments with multiple APIs:

```bash
# Start all services
docker-compose up

# This runs:
# - Weather API on port 8001  
# - Petstore API on port 8002
```

## LLM Orchestrator Configuration

For **Claude Desktop**, **Cursor**, and **Windsurf**, use the snippet below and adapt the paths accordingly:

#### Basic Configuration (FastMCP - Recommended)
```json
{
  "mcpServers": {
    "petstore3": {
      "command": "full_path_to_openapi_mcp/venv/bin/python",
      "args": ["full_path_to_openapi_mcp/src/fastmcp_server.py"],
      "env": {
        "SERVER_NAME": "petstore3",
        "OPENAPI_URL": "https://petstore3.swagger.io/api/v3/openapi.json"
      },
      "transport": "stdio"
    }
  }
}
```

#### Legacy Server (Fallback)
```json
{
  "mcpServers": {
    "petstore3_legacy": {
      "command": "full_path_to_openapi_mcp/venv/bin/python",
      "args": ["full_path_to_openapi_mcp/src/server.py"],
      "env": {
        "SERVER_NAME": "petstore3_legacy",
        "OPENAPI_URL": "https://petstore3.swagger.io/api/v3/openapi.json"
      },
      "transport": "stdio"
    }
  }
}
```

#### Norwegian Weather API (FastMCP)
```json
{
  "mcpServers": {
    "weather": {
      "command": "full_path_to_openapi_mcp/venv/bin/python",
      "args": ["full_path_to_openapi_mcp/src/fastmcp_server.py"],
      "env": {
        "SERVER_NAME": "weather",
        "OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger"
      },
      "transport": "stdio"
    }
  }
}
```

#### With Username/Password Authentication
```json
{
  "mcpServers": {
    "secure_api": {
      "command": "full_path_to_openapi_mcp/venv/bin/python",
      "args": ["full_path_to_openapi_mcp/src/server.py"],
      "env": {
        "SERVER_NAME": "secure_api",
        "OPENAPI_URL": "https://api.example.com/openapi.json",
        "API_USERNAME": "your_username",
        "API_PASSWORD": "your_password"
      },
      "transport": "stdio"
    }
  }
}
```

#### With OAuth2 Authentication
```json
{
  "mcpServers": {
    "oauth_api": {
      "command": "full_path_to_openapi_mcp/venv/bin/python",
      "args": ["full_path_to_openapi_mcp/src/server.py"],
      "env": {
        "SERVER_NAME": "oauth_api",
        "OPENAPI_URL": "https://api.example.com/openapi.json",
        "OAUTH_CLIENT_ID": "your_client_id",
        "OAUTH_CLIENT_SECRET": "your_client_secret",
        "OAUTH_TOKEN_URL": "https://api.example.com/oauth/token"
      },
      "transport": "stdio"
    }
  }
}
```

#### Multiple API Servers with MCP HTTP Transport

Configure multiple OpenAPI services to run simultaneously:

```json
{
  "mcpServers": {
    "weather": {
      "command": "npx",
      "args": [
        "mcp-remote", 
        "http://127.0.0.1:8001/sse"
      ]
    },
    "petstore": {
      "command": "npx", 
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8002/sse" 
      ]
    }
  }
}
```

This configuration gives Claude access to both weather data AND petstore API tools simultaneously, with clear tool naming like `weather_get__compact` and `petstore_addPet`.

#### Single API Server with MCP HTTP Transport

For a single API service:

**Standard SSE Configuration:**
```json
{
  "mcpServers": {
    "openapi_service": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8001/sse"
      ]
    }
  }
}
```

**Streamable HTTP Configuration:**
```json
{
  "mcpServers": {
    "openapi_service": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8001/mcp"
      ]
    }
  }
}
```

**With Debugging (for development):**
```json
{
  "mcpServers": {
    "openapi_service": {
      "command": "npx",
      "args": [
        "mcp-remote", 
        "http://127.0.0.1:8001/sse",
        "--debug"
      ]
    }
  }
}
```

**With Custom Transport Strategy:**
```json
{
  "mcpServers": {
    "openapi_service": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8001/mcp", 
        "--transport",
        "streamable-http"
      ]
    }
  }
}
```

#### With Legacy SSE Streaming (Deprecated)
```json
{
  "mcpServers": {
    "streaming_api": {
      "command": "full_path_to_openapi_mcp/venv/bin/python",
      "args": ["full_path_to_openapi_mcp/src/server.py"],
      "env": {
        "SERVER_NAME": "streaming_api",
        "OPENAPI_URL": "https://api.example.com/openapi.json",
        "SSE_ENABLED": "true",
        "SSE_HOST": "127.0.0.1",
        "SSE_PORT": "8001"
      },
      "transport": "stdio"
    }
  }
}
```

Apply this configuration to the following files:

- Cursor: `~/.cursor/mcp.json`
- Windsurf: `~/.codeium/windsurf/mcp_config.json`
- Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`

> Replace `full_path_to_openapi_mcp` with your actual installation path.

### Quick Setup for Multiple APIs

Copy the provided example configuration:
```bash
cp claude_desktop_config.json ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Start both services:
```bash
# Terminal 1
source venv/bin/activate && \
OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger" \
SERVER_NAME="weather" \
MCP_HTTP_ENABLED="true" \
MCP_HTTP_PORT="8001" \
python src/fastmcp_server.py

# Terminal 2  
source venv/bin/activate && \
OPENAPI_URL="https://petstore3.swagger.io/api/v3/openapi.json" \
SERVER_NAME="petstore" \
MCP_HTTP_ENABLED="true" \
MCP_HTTP_PORT="8002" \
python src/fastmcp_server.py
```

Result: Claude gets access to both weather and petstore APIs with prefixed tool names.

### Environment Configuration

#### Core Configuration
| Variable              | Description                          | Required | Default                |
|-----------------------|--------------------------------------|----------|------------------------|
| `OPENAPI_URL`         | URL to the OpenAPI specification     | Yes      | -                      |
| `SERVER_NAME`         | MCP server name                      | No       | `openapi_proxy_server` |

#### OAuth2 Authentication
| Variable              | Description                          | Required | Default                |
|-----------------------|--------------------------------------|----------|------------------------|
| `OAUTH_CLIENT_ID`     | OAuth client ID                      | No       | -                      |
| `OAUTH_CLIENT_SECRET` | OAuth client secret                  | No       | -                      |
| `OAUTH_TOKEN_URL`     | OAuth token endpoint URL             | No       | -                      |
| `OAUTH_SCOPE`         | OAuth scope                          | No       | `api`                  |

#### Username/Password Authentication
| Variable              | Description                          | Required | Default                |
|-----------------------|--------------------------------------|----------|------------------------|
| `API_USERNAME`        | API username for authentication      | No       | -                      |
| `API_PASSWORD`        | API password for authentication      | No       | -                      |
| `API_LOGIN_ENDPOINT`  | Login endpoint URL                   | No       | Auto-detected          |

#### MCP HTTP Transport (Recommended)
| Variable              | Description                          | Required | Default                |
|-----------------------|--------------------------------------|----------|------------------------|
| `MCP_HTTP_ENABLED`    | Enable MCP HTTP transport            | No       | `false`                |
| `MCP_HTTP_HOST`       | MCP HTTP server host                 | No       | `127.0.0.1`            |
| `MCP_HTTP_PORT`       | MCP HTTP server port                 | No       | `8000`                 |
| `MCP_CORS_ORIGINS`    | CORS origins (comma-separated)       | No       | `*`                    |
| `MCP_MESSAGE_SIZE_LIMIT` | Message size limit                | No       | `4mb`                  |
| `MCP_BATCH_TIMEOUT`   | Batch timeout in seconds             | No       | `30`                   |
| `MCP_SESSION_TIMEOUT` | Session timeout in seconds           | No       | `3600`                 |

#### Legacy SSE Support (Deprecated)
| Variable              | Description                          | Required | Default                |
|-----------------------|--------------------------------------|----------|------------------------|
| `SSE_ENABLED`         | Enable SSE streaming support         | No       | `false`                |
| `SSE_HOST`            | SSE server host                      | No       | `127.0.0.1`            |
| `SSE_PORT`            | SSE server port                      | No       | `8000`                 |

## Architecture

### Modular Design

The OpenAPI-MCP server is built with a clean, modular architecture that separates concerns and promotes maintainability:

```
src/
├── server.py              # Main server class and entry point
├── config.py              # Configuration management
├── auth.py                # OAuth authentication handling
├── openapi_loader.py      # OpenAPI spec loading and parsing
├── request_handler.py     # Request preparation and validation
├── tool_factory.py        # Dynamic tool creation and metadata
├── schema_converter.py    # Schema conversion utilities
├── exceptions.py          # Custom exception hierarchy
└── __init__.py           # Package initialization
```

### Key Components

- **ServerConfig:** Centralized configuration management with validation
- **OAuthAuthenticator:** Token management with automatic caching and renewal
- **OpenAPILoader & Parser:** Robust spec loading with error handling
- **RequestHandler:** Advanced parameter parsing and request preparation
- **ToolFactory:** Dynamic tool generation with metadata building
- **SchemaConverter:** OpenAPI to MCP schema conversion
- **Custom Exceptions:** Structured error handling with JSON-RPC compliance

## How It Works

1. **Configuration Loading:** Validates environment variables and server configuration.
2. **OpenAPI Spec Loading:** Fetches and parses OpenAPI specifications with comprehensive error handling.
3. **Component Initialization:** Sets up modular components with dependency injection.
4. **Tool Registration:** Dynamically creates MCP tools from OpenAPI operations with full metadata.
5. **Resource Registration:** Converts OpenAPI schemas into MCP resources with proper URIs.
6. **Prompt Generation:** Creates contextual usage prompts and CRUD operation examples.
7. **Authentication:** Handles both OAuth2 and username/password authentication with token caching and automatic renewal.
8. **Request Processing:** Advanced parameter parsing, type conversion, and validation.
9. **Error Handling:** Comprehensive exception handling with structured error responses.

```mermaid
sequenceDiagram
    participant LLM as LLM (Claude/GPT)
    participant MCP as OpenAPI-MCP Proxy
    participant API as External API

    Note over LLM, API: Communication Process

    LLM->>MCP: 1. Initialize (initialize)
    MCP-->>LLM: Metadata, tools, resources, and prompts

    LLM->>MCP: 2. Request tools (tools_list)
    MCP-->>LLM: Detailed list of tools, resources, and prompts

    LLM->>MCP: 3. Call tool (tools_call)

    alt With OAuth2
        MCP->>API: Request OAuth2 token
        API-->>MCP: Access Token
    end

    MCP->>API: 4. Execute API call with proper formatting
    API-->>MCP: 5. API response (JSON)

    alt Type Conversion
        MCP->>MCP: 6. Convert parameters to correct data types
    end

    MCP-->>LLM: 7. Formatted response from API

    alt Dry Run Mode
        LLM->>MCP: Call with dry_run=true
        MCP-->>LLM: Display request information without executing call
    end
```

## Resources & Prompts

The server automatically generates comprehensive metadata to enhance AI integration:

### Resources
- **Schema-based Resources:** Automatically derived from OpenAPI component schemas
- **Structured URIs:** Resources are registered with consistent URIs (e.g., `/resource/{server_name}_{schema_name}`)
- **Type Conversion:** OpenAPI schemas are converted to MCP-compatible resource definitions
- **Metadata Enrichment:** Resources include server context and categorization tags

### Prompts
- **API Usage Guides:** General prompts explaining available operations and their parameters
- **CRUD Examples:** Automatically generated examples for Create, Read, Update, Delete operations
- **Contextual Guidance:** Operation-specific prompts with parameter descriptions and usage patterns
- **Server-specific Branding:** All prompts are prefixed with server name for multi-API environments

### Benefits
- **Enhanced Discoverability:** AI agents can better understand available API capabilities
- **Usage Guidance:** Prompts provide clear examples of how to use each operation
- **Type Safety:** Resource schemas ensure proper data structure understanding
- **Context Awareness:** Server-specific metadata helps with multi-API integration

![OpenAPI-MCP](https://raw.githubusercontent.com/gujord/OpenAPI-MCP/refs/heads/main/img/OpenAPI-MCP.png)

## Example: Norwegian Weather API

The Norwegian Meteorological Institute provides an excellent example of a well-designed OpenAPI that works seamlessly with our server:

```bash
# Test with Norwegian Weather API
OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger" \
SERVER_NAME="weather" \
python src/server.py
```

This integration provides:
- **12 weather operations** including compact and complete forecasts
- **Geographic coordinate support** (latitude/longitude parameters)
- **Real-time weather data** with temperature, humidity, pressure, and more
- **85+ forecast periods** for detailed weather planning
- **No authentication required** - perfect for testing basic functionality

**Example API call for Oslo weather:**
```
Tool: weather_get__compact
Parameters: lat=59.9139, lon=10.7522
Result: Current weather and 85-period forecast for Oslo
```

## MCP HTTP Transport (Official Streaming)

The server now includes official MCP-compliant HTTP transport with Server-Sent Events, following the Model Context Protocol specification for real-time streaming communication.

### Enabling MCP HTTP Transport

```bash
# Enable MCP HTTP transport
MCP_HTTP_ENABLED=true \
MCP_HTTP_HOST=127.0.0.1 \
MCP_HTTP_PORT=8001 \
OPENAPI_URL="https://api.example.com/openapi.json" \
SERVER_NAME="mcp_api" \
python src/server.py
```

### MCP Transport Features

- **JSON-RPC 2.0 Compliance**: Full JSON-RPC message handling over HTTP and SSE
- **Session Management**: Unique session IDs with automatic cleanup
- **Batch and Streaming Modes**: Support for both immediate and streaming responses
- **Official MCP Endpoints**: Standard MCP HTTP endpoints according to specification
- **CORS Support**: Configurable CORS for web client integration

### MCP Endpoints

When MCP HTTP transport is enabled, the following endpoints are available:

**Standard mcp-remote endpoints:**
- `GET /sse` - SSE endpoint for mcp-remote clients
- `POST /mcp` - Main MCP JSON-RPC endpoint  
- `GET /health` - Health check

**Advanced endpoints:**
- `GET /mcp/sse/{session_id}` - Session-specific SSE stream
- `DELETE /mcp/sessions/{session_id}` - Terminate specific session
- `GET /mcp/health` - Detailed health information

## Legacy SSE Streaming (Deprecated)

> **Note**: The legacy SSE implementation is deprecated. Use MCP HTTP transport for official MCP compliance.

For backward compatibility, the legacy SSE streaming is still available but not recommended for new implementations.

### Using MCP HTTP Transport

**With mcp-remote (Recommended):**

Simply configure your MCP client with `mcp-remote` and it handles all the communication:

```json
{
  "mcpServers": {
    "openapi_service": {
      "command": "npx",
      "args": ["mcp-remote", "http://127.0.0.1:8001/sse"]
    }
  }
}
```

**Direct API Usage (Advanced):**

```javascript
// 1. Connect to SSE stream
const eventSource = new EventSource('http://127.0.0.1:8001/sse');

eventSource.addEventListener('connected', function(event) {
  const data = JSON.parse(event.data);
  console.log('Connected to MCP server:', data.server_info.name);
  
  // 2. Send JSON-RPC requests via POST /mcp
  sendMcpRequest({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {}
    }
  }, data.session_id);
});

eventSource.addEventListener('response', function(event) {
  const response = JSON.parse(event.data);
  console.log('MCP Response:', response);
});

async function sendMcpRequest(request, sessionId) {
  await fetch('http://127.0.0.1:8001/mcp', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Mcp-Session-Id': sessionId
    },
    body: JSON.stringify(request)
  });
}
```

## Development & Testing

### Code Quality
- **Type Safety:** Full type hints throughout the codebase
- **Error Handling:** Comprehensive exception hierarchy with proper error codes
- **Logging:** Structured logging with appropriate levels for debugging
- **Documentation:** Extensive docstrings and clear module organization

### Extensibility
- **Factory Patterns:** Easy to extend tool creation and metadata building
- **Dependency Injection:** Components can be easily mocked and tested
- **Modular Design:** Each module has a single responsibility and clear interfaces
- **Configuration Management:** Centralized config with validation and defaults

## Contributing

- Fork this repository.
- Create a new branch.
- Submit a pull request with a clear description of your changes.

## License

[MIT License](LICENSE)

If you find it useful, please give it a ⭐ on GitHub!
