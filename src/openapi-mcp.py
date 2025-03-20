import os
import sys
import json
import httpx
import logging
import argparse
from urllib.parse import urljoin, urlparse
from typing import Any, Dict, Tuple
import yaml

from mcp.server.fastmcp import FastMCP

# Configure logging for both console and file (if needed)
logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Global variables for MCP instance and OpenAPI operations info
mcp = None
operations_info: Dict[str, Dict[str, Any]] = {}

def initialize_mcp(server_name: str = "openapi_proxy_server") -> FastMCP:
    """
    Initialize the MCP server with the specified server name.
    Sets server capabilities and prepares for tool registration.
    """
    global mcp
    mcp = FastMCP(server_name)
    mcp.server_name = server_name
    # Define MCP server capabilities; tools capability is enabled.
    mcp.capabilities = {
        "tools": {
            "listChanged": True
        }
    }
    return mcp

###############################################################################
# OAuth client_credentials authentication support
###############################################################################
def get_oauth_access_token() -> str:
    """
    Obtain an OAuth access token using client_credentials flow.
    Expects environment variables: OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_SCOPE, OAUTH_TOKEN_URL.
    """
    oauth_client_id = os.environ.get("OAUTH_CLIENT_ID")
    oauth_client_secret = os.environ.get("OAUTH_CLIENT_SECRET")
    oauth_scope = os.environ.get("OAUTH_SCOPE", "api")
    oauth_token_url = os.environ.get("OAUTH_TOKEN_URL")
    if oauth_client_id and oauth_client_secret and oauth_token_url:
        try:
            response = httpx.post(
                oauth_token_url,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "client_credentials",
                    "client_id": oauth_client_id,
                    "client_secret": oauth_client_secret,
                    "scope": oauth_scope
                }
            )
            response.raise_for_status()
            token_data = response.json()
            logging.info("Obtained OAuth access token.")
            return token_data.get("access_token")
        except Exception as e:
            logging.error("Error obtaining access token: %s", str(e))
            sys.exit(1)
    logging.info("No OAuth credentials provided; continuing without access token.")
    return None

###############################################################################
# OpenAPI loading and endpoint extraction (supports JSON or YAML)
###############################################################################
def load_openapi(openapi_url: str) -> Tuple[Dict[str, Any], str, Dict[str, Dict[str, Any]]]:
    """
    Load the OpenAPI specification from a URL (JSON or YAML) and extract:
    - The specification document.
    - The base server URL.
    - Operations info mapping operationId to details (summary, parameters, path, method).
    """
    try:
        spec_response = httpx.get(openapi_url)
        spec_response.raise_for_status()
        try:
            openapi_spec = spec_response.json()
        except Exception:
            openapi_spec = yaml.safe_load(spec_response.text)
    except Exception as e:
        logging.error("Could not load OpenAPI specification: %s", e)
        sys.exit(1)

    try:
        raw_server_url = openapi_spec["servers"][0]["url"]
    except (KeyError, IndexError):
        parsed = urlparse(openapi_url)
        base_path = parsed.path.rsplit('/', 1)[0]
        raw_server_url = f"{parsed.scheme}://{parsed.netloc}{base_path}"
    if raw_server_url.startswith("/"):
        parsed_openapi = urlparse(openapi_url)
        server_url = urljoin(f"{parsed_openapi.scheme}://{parsed_openapi.netloc}", raw_server_url)
    elif not raw_server_url.startswith(("http://", "https://")):
        server_url = f"https://{raw_server_url}"
    else:
        server_url = raw_server_url

    ops_info = {}
    for path, path_item in openapi_spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch", "head", "options"]:
                continue
            operation_id = operation.get("operationId")
            if not operation_id:
                sanitized = path.replace("/", "_").replace("{", "").replace("}", "")
                operation_id = f"{method}_{sanitized}"
            ops_info[operation_id] = {
                "summary": operation.get("summary", ""),
                "parameters": operation.get("parameters", []),
                "path": path,
                "method": method.upper()
            }
    logging.info("Loaded %d operations from OpenAPI spec.", len(ops_info))
    return openapi_spec, server_url, ops_info

###############################################################################
# Helper: Return tools list as JSON object compliant with MCP tools/list response
###############################################################################
def get_tools_json(ops_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a JSON object listing available tools with metadata, following MCP standards.
    """
    tools = []
    for op_id, info in ops_info.items():
        properties = {}
        required = []
        for param in info.get("parameters", []):
            name = param.get("name")
            p_type = param.get("schema", {}).get("type", "string")
            description = param.get("description", "")
            properties[name] = {"type": p_type, "description": description}
            if param.get("required", False):
                required.append(name)
        input_schema = {"type": "object", "properties": properties}
        if required:
            input_schema["required"] = required
        tools.append({
            "name": op_id,
            "description": info.get("summary", op_id),
            "inputSchema": input_schema
        })
    return {
        "tools": tools,
        "nextCursor": None,
        "capabilities": {
            "tools": {
                "listChanged": True
            }
        }
    }

###############################################################################
# Helper: Return help for a specific endpoint as JSON object (JSON-RPC compliant)
###############################################################################
def get_endpoint_help_json(endpoint: str, ops_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Provide detailed help for a given endpoint, including HTTP method, path, summary, parameters, and global options.
    """
    info = ops_info.get(endpoint)
    if not info:
        return {"error": f"Endpoint not found: {endpoint}"}
    help_info = {
        "endpoint": endpoint,
        "method": info.get("method", ""),
        "path": info.get("path", ""),
        "summary": info.get("summary", ""),
        "parameters": info.get("parameters", []),
        "global_options": {
            "--dry-run": "Simulate execution without making an API call",
            "--param": "Provide parameters in key=value format (can be repeated)"
        }
    }
    return {"help": help_info}

###############################################################################
# Tool function generator with dry-run support and robust error handling.
###############################################################################
def generate_tool_function(operation_id: str, method: str, path: str, parameters: list,
                             server_url: str, ops_info: Dict[str, Any], client: httpx.Client):
    """
    Create a function that wraps an API endpoint call.
    The generated tool supports dry-run, parameter processing, OAuth authentication,
    and logs progress using the optional context (ctx) parameter.
    """
    def tool_func(**kwargs):
        # Extract and use context for logging if provided.
        ctx = kwargs.pop("ctx", None)
        if ctx:
            ctx.info(f"Executing endpoint: {operation_id}")
        else:
            logging.info("Executing endpoint: %s", operation_id)

        # Check for missing required parameters.
        missing_params = []
        for param in parameters:
            if param.get("required", False) and (param["name"] not in kwargs):
                missing_params.append(param["name"])
        if missing_params:
            help_json = get_endpoint_help_json(operation_id, ops_info)
            return {
                "jsonrpc": "2.0",
                "id": 0,
                "server_name": mcp.server_name if mcp else None,
                "result": help_json
            }

        dry_run = kwargs.pop("dry_run", False)
        request_params = {}
        request_headers = {}
        request_body = None

        # Process each parameter based on its location.
        for param in parameters:
            name = param["name"]
            location = param.get("in", "query")
            schema_type = param.get("schema", {}).get("type", "string")
            if name in kwargs:
                value = kwargs[name]
                if schema_type == "integer":
                    value = int(value)
                elif schema_type == "number":
                    value = float(value)
                elif schema_type == "boolean":
                    value = str(value).lower() in ("true", "1", "yes", "y")

                if location == "path":
                    path_local = path.replace(f"{{{name}}}", str(value))
                    path = path_local
                elif location == "query":
                    request_params[name] = value
                elif location == "header":
                    request_headers[name] = value
                elif location == "body":
                    request_body = value

        # Apply OAuth if available.
        oauth_token = get_oauth_access_token()
        if oauth_token:
            request_headers["Authorization"] = f"Bearer {oauth_token}"

        full_url = urljoin(server_url, path)
        if dry_run:
            dry_run_output = {
                "dry_run": True,
                "description": "This is a simulated API call. No request was sent.",
                "request": {
                    "url": full_url,
                    "method": method.upper(),
                    "headers": request_headers,
                    "params": request_params,
                    "body": request_body
                }
            }
            return {
                "jsonrpc": "2.0",
                "id": 0,
                "server_name": mcp.server_name if mcp else None,
                "result": dry_run_output
            }

        try:
            response = client.request(
                method=method,
                url=full_url,
                params=request_params,
                headers=request_headers,
                json=request_body if request_body else None
            )
            response.raise_for_status()
            try:
                response_data = response.json()
            except Exception:
                response_data = {"raw_response": response.text}
            if ctx:
                ctx.info(f"Endpoint {operation_id} executed successfully.")
            else:
                logging.info("Endpoint %s executed successfully.", operation_id)
            return {
                "jsonrpc": "2.0",
                "id": 0,
                "server_name": mcp.server_name if mcp else None,
                "result": response_data
            }
        except Exception as e:
            error_message = f"Error executing endpoint {operation_id}: {e}"
            if ctx:
                ctx.error(error_message)
            else:
                logging.error(error_message)
            return {
                "jsonrpc": "2.0",
                "id": 0,
                "server_name": mcp.server_name if mcp else None,
                "error": {"code": -32000, "message": str(e)}
            }
    return tool_func

###############################################################################
# Named tool function to expose tools as capabilities.
###############################################################################
def metadata_tool() -> Dict[str, Any]:
    """
    Return a list of available tools and their metadata in MCP tools/list format.
    """
    return get_tools_json(operations_info)

###############################################################################
# MCP API command handler (returns JSON-RPC 2.0 responses)
###############################################################################
def mcp_api_handler(args: argparse.Namespace):
    global operations_info

    # Prefer command-line argument over environment variable for OpenAPI URL.
    openapi_url = args.openapi_url if args.openapi_url else os.environ.get("OPENAPI_URL")
    if not openapi_url:
        error_output = {
            "jsonrpc": "2.0",
            "id": 0,
            "server_name": mcp.server_name if mcp else None,
            "error": {"code": -32602, "message": "OPENAPI_URL not provided. Set via --openapi-url or environment variable."}
        }
        print(json.dumps(error_output, indent=2))
        sys.exit(1)

    if args.action == "help":
        help_json = {
            "commands": {
                "tools-list": "List available tools and capabilities",
                "call-endpoint": "Call a specific endpoint with parameters",
                "help": "Display help message for API commands"
            }
        }
        output = {
            "jsonrpc": "2.0",
            "id": 0,
            "server_name": mcp.server_name if mcp else None,
            "result": help_json
        }
        print(json.dumps(output, indent=2))
        return

    # Load OpenAPI spec and extract operations info.
    _, server_url, operations_info = load_openapi(openapi_url)
    client = httpx.Client()

    # Register each OpenAPI endpoint as an MCP tool.
    for operation_id, info in operations_info.items():
        tool_func = generate_tool_function(
            operation_id=operation_id,
            method=info["method"],
            path=info["path"],
            parameters=info.get("parameters", []),
            server_url=server_url,
            ops_info=operations_info,
            client=client
        )
        globals()[operation_id] = mcp.tool()(tool_func)

    # Register the tools listing as an MCP tool with the reserved name "tools/list".
    globals()["tools/list"] = mcp.tool(
        name="tools/list",
        description="List available tools and capabilities"
    )(metadata_tool)

    # Process API actions.
    if args.action == "tools-list":
        result = globals()["tools/list"]()
        print(json.dumps(result, indent=2))
    elif args.action == "call-endpoint":
        if not args.name:
            error_output = {
                "jsonrpc": "2.0",
                "id": 0,
                "server_name": mcp.server_name if mcp else None,
                "error": {"code": -32602, "message": "Endpoint name is required. Use tools-list to view available tools."}
            }
            print(json.dumps(error_output, indent=2))
            return
        endpoint_name = args.name
        if endpoint_name not in operations_info:
            error_output = {
                "jsonrpc": "2.0",
                "id": 0,
                "server_name": mcp.server_name if mcp else None,
                "error": {"code": -32601, "message": f"Endpoint '{endpoint_name}' not found."}
            }
            print(json.dumps(error_output, indent=2))
            return

        params = {}
        if args.param:
            for param_str in args.param:
                try:
                    key, value = param_str.split("=", 1)
                    params[key] = value
                except ValueError:
                    error_output = {
                        "jsonrpc": "2.0",
                        "id": 0,
                        "server_name": mcp.server_name if mcp else None,
                        "error": {"code": -32602, "message": f"Invalid parameter format: {param_str}. Use key=value format."}
                    }
                    print(json.dumps(error_output, indent=2))
                    return

        params["dry_run"] = args.dry_run

        if args.command_help == "help":
            help_output = get_endpoint_help_json(endpoint_name, operations_info)
            output = {
                "jsonrpc": "2.0",
                "id": 0,
                "server_name": mcp.server_name if mcp else None,
                "result": help_output
            }
            print(json.dumps(output, indent=2))
        else:
            if endpoint_name in globals():
                result = globals()[endpoint_name](**params)
            else:
                error_output = {
                    "jsonrpc": "2.0",
                    "id": 0,
                    "server_name": mcp.server_name if mcp else None,
                    "error": {"code": -32601, "message": f"Endpoint '{endpoint_name}' not found or not properly registered."}
                }
                print(json.dumps(error_output, indent=2))
                return
            print(json.dumps(result, indent=2))
    client.close()

###############################################################################
# Main entry point
###############################################################################
def main():
    parser = argparse.ArgumentParser(
        prog="openapi-mcp",
        description="CLI for OpenAPI-based API calls (JSON-RPC 2.0 compliant MCP server)"
    )
    parser.add_argument("--server", default="openapi_proxy_server",
                        help="MCP server name to use (default: openapi_proxy_server)")
    parser.add_argument("--openapi-url", help="URL of the OpenAPI specification")
    subparsers = parser.add_subparsers(dest="service", required=True, help="Service (e.g., api)")

    api_parser = subparsers.add_parser("api", help="API service commands")
    api_subparsers = api_parser.add_subparsers(dest="action", required=True, help="Action to perform")

    api_subparsers.add_parser("help", help="Show help for API commands")
    tools_list_parser = api_subparsers.add_parser("tools-list", help="List available tools and capabilities")
    tools_list_parser.add_argument("--output", default="json", help="Output format (always json)")

    call_parser = api_subparsers.add_parser("call-endpoint", help="Call a specific API endpoint")
    call_parser.add_argument("--name", help="Endpoint name to call")
    call_parser.add_argument("--param", action="append", help="Parameter for the API call (key=value). Can be specified multiple times.")
    call_parser.add_argument("--dry-run", action="store_true", help="Simulate execution without making an API call")
    call_parser.add_argument("--output", default="json", help="Output format (always json)")
    call_parser.add_argument("command_help", nargs="?", default="", help="If set to 'help', display help for call-endpoint")

    args = parser.parse_args()

    initialize_mcp(args.server)

    if args.service == "api":
        mcp_api_handler(args)
    else:
        error_output = {
            "jsonrpc": "2.0",
            "id": 0,
            "server_name": mcp.server_name if mcp else None,
            "error": {"code": -32600, "message": f"Unknown service: {args.service}"}
        }
        print(json.dumps(error_output, indent=2))
        parser.print_help()

if __name__ == "__main__":
    main()
