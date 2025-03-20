# OpenAPI-MCP

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Repo Size](https://img.shields.io/github/repo-size/gujord/OpenAPI-MCP)
![Last Commit](https://img.shields.io/github/last-commit/gujord/OpenAPI-MCP)
![Open Issues](https://img.shields.io/github/issues/gujord/OpenAPI-MCP)

OpenAPI-MCP is a command-line interface (CLI) tool that leverages an OpenAPI specification to dynamically generate and call API endpoints. The tool integrates with the Model Context Protocol (MCP) so that large language models (LLMs) can use these endpoints as callable tools.

![Alt text](OpenAPI-MCP.png)

## Features

- **Dynamic Endpoint Generation:** Load OpenAPI specifications (in JSON or YAML) and extract API endpoint details.
- **Multiple Output Formats:** Supports JSON, YAML, XML, and Markdown.
- **Error & Help Documentation:** Provides detailed help messages when required parameters are missing or an endpoint is unknown.
- **Authentication Support:** Can use a direct access token or perform an OAuth client_credentials flow.
- **LLM Integration via MCP:** Registers endpoints as callable functions so LLMs can directly invoke them.

## Prerequisites

- Python 3.7 or later.
- A virtual environment is recommended.
- Required packages are listed in `requirements.txt`.

## Setup Instructions

1. **Create a Virtual Environment:**

   ```bash
   python3 -m venv venv
   ```

2. **Activate the Virtual Environment:**

   - On Linux/macOS:

     ```bash
     source venv/bin/activate
     ```

   - On Windows:

     ```bash
     venv\Scripts\activate
     ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables

Before running the tool, set the necessary environment variables.

### OpenAPI Specification

- **OPENAPI_URL**: URL to your OpenAPI specification (JSON or YAML).  
  Example:

  ```bash
  export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger"
  ```

### OAuth Authentication (Optional)

If your API requires OAuth authentication using the client_credentials flow, set:

- **OAUTH_CLIENT_ID**
- **OAUTH_CLIENT_SECRET**
- **OAUTH_SCOPE** (defaults to `api` if not set)
- **OAUTH_TOKEN_URL**

Alternatively, if you already have an access token, set:

- **AUTH_TOKEN**

## Usage

### Listing Endpoints

List all available endpoints defined in the OpenAPI spec. Supported output formats are: `json`, `yaml`, `xml`, and `markdown`.

```bash
python3 src/openapi-mcp.py api list-endpoints --output json
```

Example using YAML output:

```bash
export OPENAPI_URL="https://nvdbapiles.atlas.vegvesen.no/openapi.yaml"
python3 src/openapi-mcp.py api list-endpoints --output yaml
```

### Getting Help for an Endpoint

To get detailed help about a specific endpoint, including parameter details, run:

```bash
python3 src/openapi-mcp.py api call-endpoint --name <endpoint_name> help
```

Example:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact help
```

*Note:* If an endpoint does not provide a description, only the endpoint name will be listed.

### Calling an Endpoint

To call an endpoint, provide the endpoint name along with any required parameters using the `--param` option:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10
```

To simulate a request without actually sending it, use the `--dry-run` flag:

```bash
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10 --dry-run
```

## Using OpenAPI-MCP with LLMs via MCP

OpenAPI-MCP integrates with the Model Context Protocol (MCP) to expose API endpoints as callable tools. When the tool starts, it:

- **Loads the OpenAPI Spec:** Dynamically extracts endpoints and registers them.
- **Registers Tools with MCP:** Each endpoint is registered as a callable function via `mcp.tool()`.
- **LLM Invocation:** A large language model (LLM) can then use these functions to query APIs directly. When an LLM recognizes a need for external data, it can invoke a registered tool by its operation ID, passing along the required parameters. The tool validates the input and returns formatted output in the desired format.

This integration extends the capabilities of an LLM by enabling it to interact with external APIs, enriching the context and precision of its responses.

## Examples

### Example 1: List Endpoints (YAML Format)

```bash
export OPENAPI_URL="https://nvdbapiles.atlas.vegvesen.no/openapi.yaml"
python3 src/openapi-mcp.py api list-endpoints --output yaml
```

### Example 2: Get Endpoint Help

```bash
export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger"
python3 src/openapi-mcp.py api call-endpoint --name get__compact help
```

### Example 3: Call an Endpoint with Parameters

```bash
export OPENAPI_URL="https://api.met.no/weatherapi/locationforecast/2.0/swagger"
python3 src/openapi-mcp.py api call-endpoint --name get__compact --param lat=60 --param lon=10
```

## Troubleshooting

- **OPENAPI_URL:** Ensure the URL is accessible and points to a valid OpenAPI specification.
- **OAuth Setup:** Verify that your OAuth-related environment variables are correct if authentication is required.
- **Parameter Errors:** Use the `--dry-run` flag to debug parameter issues before making live API calls.

## License & Credits

For license information, see the LICENSE file.  
For further details on API client registration and usage, please refer to the respective API provider’s documentation.
