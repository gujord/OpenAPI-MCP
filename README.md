# OpenAPI to Model Context Protocol

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Repo Size](https://img.shields.io/github/repo-size/gujord/OpenAPI-MCP)
![Last Commit](https://img.shields.io/github/last-commit/gujord/OpenAPI-MCP)
![Open Issues](https://img.shields.io/github/issues/gujord/OpenAPI-MCP)

OpenAPI-MCP makes any API available to Large Language Models (LLMs) through the Model Context Protocol (MCP). It automatically reads OpenAPI/Swagger specifications and dynamically registers endpoints, enabling LLMs to seamlessly interact with external APIs.

If you like the direction of this project, consider giving it a ⭐ on GitHub!

![OpenAPI-MCP](OpenAPI-MCP.png)

## Features

- **Dynamic Endpoint Generation:** Loads OpenAPI specifications (JSON/YAML) to extract API endpoint details automatically.
- **JSON-RPC 2.0 Compliance:** All responses conform to the JSON-RPC 2.0 standard, with a top-level `server_name` field for seamless integration.
- **Error & Help Documentation:** Detailed messages are provided for missing parameters or unknown endpoints.
- **Authentication Support:** Supports both direct access tokens and OAuth client_credentials authentication.
- **LLM Integration via MCP:** Endpoints are registered as callable tools, enabling direct invocation by LLMs. This generic MCP server output is compatible with integrations like cursor and windsurf.

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

Set necessary environment variables before running:

### OpenAPI Specification

- **OPENAPI_URL**: URL pointing to your OpenAPI specification (JSON/YAML).

  ```bash
  export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger"
  ```

### OAuth Authentication (Optional)

If using OAuth client_credentials authentication, set:

- **OAUTH_CLIENT_ID**
- **OAUTH_CLIENT_SECRET**
- **OAUTH_SCOPE** (default: `api`)
- **OAUTH_TOKEN_URL**

Alternatively, for direct access tokens, set:

- **AUTH_TOKEN**

## Model Context Protocol (MCP) Configuration

The MCP integration now returns JSON-RPC 2.0 responses with a top-level `server_name` field. This structure makes it easy to integrate with MCP orchestrators (e.g., cursor and windsurf). For example, include the following configuration in your MCP setup:

```json
{
    "mcpServers": {
        "locationforecast": {
            "command": "bash",
            "args": [
                "-c",
                "source venv/bin/activate && python3 src/openapi-mcp.py --server locationforecast api list-endpoints"
            ],
            "env": {
                "OPENAPI_URL": "https://api.met.no/weatherapi/locationforecast/2.0/swagger"
            }
        }
    }
}
```

This configuration demonstrates a generic MCP server that can be registered and invoked by external LLM integrations.

## Usage

### List Available Endpoints

List endpoints from the OpenAPI spec. The response is a JSON-RPC 2.0 message that includes a top-level `server_name` field:

```bash
python3 src/openapi-mcp.py api list-endpoints --output json
```

Example (YAML):

```bash
export OPENAPI_URL="https://nvdbapiles.atlas.vegvesen.no/openapi.yaml"
python3 src/openapi-mcp.py api list-endpoints --output yaml
```

### Get Endpoint Help

Retrieve detailed help on endpoint parameters and usage:

```bash
python3 src/openapi-mcp.py api call-endpoint --name <endpoint_name> help
```

Example:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact help
```

### Call an Endpoint

Invoke an endpoint with parameters. The response will follow the JSON-RPC 2.0 standard:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10
```

Dry-run mode for testing parameters without sending a request:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10 --dry-run
```

## Integration with LLMs via MCP

OpenAPI-MCP integrates with MCP, enabling LLMs to directly invoke API endpoints:

- **Dynamic Registration:** Endpoints from the OpenAPI spec are automatically loaded and registered as MCP tools.
- **LLM Invocation:** LLMs call endpoints using registered operation IDs, with all responses formatted according to JSON-RPC 2.0 (including a top-level `server_name`).
- **Generic Server:** The MCP server is generic and can work with various orchestrators (like cursor and windsurf) without modification.

This integration extends LLM capabilities by facilitating structured interaction with external APIs.

## Examples

### Example 1: List Endpoints (YAML)

```bash
export OPENAPI_URL="https://nvdbapiles.atlas.vegvesen.no/openapi.yaml"
python3 src/openapi-mcp.py api list-endpoints --output yaml
```

### Example 2: Endpoint Help

```bash
export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger"
python3 src/openapi-mcp.py api call-endpoint --name get__compact help
```

### Example 3: Endpoint Call with Parameters

```bash
export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger"
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10
```

## Troubleshooting

- **OPENAPI_URL:** Ensure the OpenAPI specification is accessible and correctly formatted.
- **OAuth Errors:** Verify that all required OAuth environment variables are set properly.
- **Parameter Issues:** Use the `--dry-run` flag to validate parameters before executing an API call.

## Contributions

Contributions are welcome. Please open an issue or submit a pull request.

If you like the direction of this project, consider giving it a ⭐ on GitHub!

## License & Credits

Refer to [LICENSE](LICENSE) for license details (MIT). For API-specific client registration, refer to the respective API provider's documentation.
```
