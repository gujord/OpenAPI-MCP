import os
import sys
import json
import httpx
import logging
from urllib.parse import urljoin, urlparse
from typing import Any, Dict, Tuple, List, Optional
import yaml

from mcp.server.fastmcp import FastMCP, tools

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

mcp: Optional[FastMCP] = None
operations_info: Dict[str, Dict[str, Any]] = {}

def initialize_mcp(server_name: str = "openapi_proxy_server") -> FastMCP:
    global mcp
    mcp = FastMCP(server_name)
    return mcp

def get_oauth_access_token() -> Optional[str]:
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

def load_openapi(openapi_url: str) -> Tuple[Dict[str, Any], str, Dict[str, Dict[str, Any]]]:
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

    raw_server_url = ""
    servers = openapi_spec.get("servers")
    if isinstance(servers, list) and servers:
        raw_server_url = servers[0].get("url", "")
    elif isinstance(servers, dict):
        raw_server_url = servers.get("url", "")
    if not raw_server_url:
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

    ops_info: Dict[str, Dict[str, Any]] = {}
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

def get_tool_metadata(ops_info: Dict[str, Any]) -> Dict[str, Any]:
    tools_list: List[Dict[str, Any]] = []
    for op_id, info in ops_info.items():
        properties = {}
        required: List[str] = []
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
        tools_list.append({
            "name": op_id,
            "description": info.get("summary", op_id),
            "inputSchema": input_schema
        })
    return {"tools": tools_list}

# Fjern dekoratøren; definer metadata_tool som en vanlig funksjon.
def metadata_tool() -> Dict[str, Any]:
    return get_tool_metadata(operations_info)

def generate_tool_function(operation_id: str, method: str, path: str, parameters: List[Dict[str, Any]],
                           server_url: str, ops_info: Dict[str, Any], client: httpx.Client):
    def tool_func(**kwargs):
        local_path = path
        ctx = kwargs.pop("ctx", None)
        if ctx:
            ctx.info(f"Executing endpoint: {operation_id}")
        else:
            logging.info("Executing endpoint: %s", operation_id)

        missing_params: List[str] = []
        for param in parameters:
            if param.get("required", False) and (param["name"] not in kwargs):
                missing_params.append(param["name"])
        if missing_params:
            return {"error": f"Missing required parameters: {', '.join(missing_params)}"}

        dry_run = kwargs.pop("dry_run", False)
        request_params = {}
        request_headers = {}
        request_body = None

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
                    local_path = local_path.replace(f"{{{name}}}", str(value))
                elif location == "query":
                    request_params[name] = value
                elif location == "header":
                    request_headers[name] = value
                elif location == "body":
                    request_body = value

        oauth_token = get_oauth_access_token()
        if oauth_token:
            request_headers["Authorization"] = f"Bearer {oauth_token}"

        full_url = urljoin(server_url, local_path)
        if dry_run:
            return {
                "dry_run": True,
                "description": "Simulated API call. No request sent.",
                "request": {
                    "url": full_url,
                    "method": method.upper(),
                    "headers": request_headers,
                    "params": request_params,
                    "body": request_body
                }
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
            return response_data
        except httpx.HTTPStatusError as e:
            error_message = f"HTTP error executing endpoint {operation_id}: {e.response.status_code} - {e.response.text}"
            if ctx:
                ctx.error(error_message)
            else:
                logging.error(error_message)
            return {"isError": True, "content": [{"type": "text", "text": error_message}]}
        except Exception as e:
            error_message = f"Error executing endpoint {operation_id}: {e}"
            if ctx:
                ctx.error(error_message)
            else:
                logging.error(error_message)
            return {"isError": True, "content": [{"type": "text", "text": str(e)}]}
    return tool_func

def get_endpoint_help_json(endpoint: str, ops_info: Dict[str, Any]) -> Dict[str, Any]:
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
            "dry_run": "Simulate execution without making an API call"
        }
    }
    return {"help": help_info}

def register_openapi_tools():
    global operations_info, mcp
    if mcp is None:
        logging.error("MCP server not initialized.")
        return

    openapi_url = os.environ.get("OPENAPI_URL")
    if openapi_url:
        _, server_url, operations_info = load_openapi(openapi_url)
        client = httpx.Client()
        for operation_id, info in operations_info.items():
            tool_function = generate_tool_function(
                operation_id=operation_id,
                method=info["method"],
                path=info["path"],
                parameters=info.get("parameters", []),
                server_url=server_url,
                ops_info=operations_info,
                client=client
            )
            mcp.add_tool(tool_function, name=operation_id, description=info.get("summary", operation_id))
        client.close()
    else:
        operations_info = {}

    # Registrer metadata_tool eksplisitt
    mcp.add_tool(metadata_tool, name="tools_list", description="List available tools and capabilities")

def main():
    server_name = os.environ.get("MCP_SERVER", "openapi_proxy_server")
    mcp_instance = initialize_mcp(server_name)
    register_openapi_tools()
    mcp_instance.run()

if __name__ == "__main__":
    main()
