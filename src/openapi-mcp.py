import os
import sys
import json
import httpx
import logging
import re
import asyncio
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
# Global SSE queue to hold JSON-RPC responses to be streamed
sse_queue: Optional[asyncio.Queue] = None

def sanitize_tool_name(name: str) -> str:
    """
    Sanitizes the tool name so that it contains only letters, numbers, underscores, and hyphens.
    Replaces invalid characters with underscores and limits the length to 64 characters.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return sanitized[:64]

def initialize_mcp(server_name: str = "openapi_proxy_server") -> FastMCP:
    global mcp
    mcp = FastMCP(server_name)
    # Explicitly set server_name attribute for inclusion in responses.
    mcp.server_name = server_name
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
        safe_op_id = sanitize_tool_name(op_id)
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
            "name": safe_op_id,
            "description": info.get("summary", op_id),
            "inputSchema": input_schema
        })
    return {"tools": tools_list}

def metadata_tool(req_id: Any = None) -> Dict[str, Any]:
    tools_list: List[Dict[str, Any]] = []
    for op_id, info in operations_info.items():
        safe_op_id = sanitize_tool_name(op_id)
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
            "name": safe_op_id,
            "description": info.get("summary", op_id),
            "inputSchema": input_schema
        })
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "server_name": mcp.server_name if mcp else None,
        "result": tools_list
    }

def generate_tool_function(operation_id: str, method: str, path: str, parameters: List[Dict[str, Any]],
                           server_url: str, ops_info: Dict[str, Any], client: httpx.Client):
    def tool_func(req_id: Any = None, **kwargs):
        local_path = path
        missing_params = []
        for param in parameters:
            if param.get("required", False) and (param["name"] not in kwargs):
                missing_params.append(param["name"])
        if missing_params:
            help_json = get_endpoint_help_json(operation_id, ops_info)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "server_name": mcp.server_name if mcp else None,
                "result": help_json
            }
        
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
            dry_run_output = {
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
            return {
                "jsonrpc": "2.0",
                "id": req_id,
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
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "server_name": mcp.server_name if mcp else None,
                "result": response_data
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "server_name": mcp.server_name if mcp else None,
                "error": {"code": -32000, "message": str(e)}
            }
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
    return {"server_name": mcp.server_name if mcp else None, "help": help_info}

#############################################
# SSE and JSON-RPC endpoints for Cursor support
#############################################
def run_sse_app(mcp_instance: FastMCP):
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse, JSONResponse
    import uvicorn

    app = FastAPI()
    global sse_queue
    sse_queue = asyncio.Queue()

    @app.post("/jsonrpc")
    async def jsonrpc_endpoint(request: Request):
        try:
            data = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400, 
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "server_name": mcp_instance.server_name,
                    "error": {"code": -32700, "message": "Invalid JSON"}
                }
            )
        
        method = data.get("method")
        params = data.get("params", {})
        req_id = data.get("id")
        if mcp_instance.tools and method in mcp_instance.tools:
            try:
                # Pass the request ID to the tool function
                result = mcp_instance.tools[method](req_id=req_id, **params)
                # The tool function now returns the complete response with correct ID
                response = result
            except Exception as e:
                logging.error("Exception occurred: %s", str(e))
                response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": "An internal error has occurred"},
                    "id": req_id,
                    "server_name": mcp_instance.server_name
                }
        else:
            response = {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "Method not found"},
                "id": req_id,
                "server_name": mcp_instance.server_name
            }
        await sse_queue.put(response)
        return JSONResponse(content=response)

    @app.get("/sse")
    async def sse_endpoint(request: Request):
        async def event_generator():
            # Use a specific ID for the initial metadata message
            initial_response = metadata_tool(req_id=1)
            yield f"data: {json.dumps(initial_response)}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(sse_queue.get(), timeout=5.0)
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # Use a specific ID for heartbeat messages
                    heartbeat = {
                        "jsonrpc": "2.0",
                        "result": {"heartbeat": "keep-alive"},
                        "id": 0,
                        "server_name": mcp_instance.server_name
                    }
                    yield f"data: {json.dumps(heartbeat)}\n\n"
        return StreamingResponse(event_generator(), media_type="text/event-stream")

    uvicorn.run(app, host="0.0.0.0", port=8000)

#############################################
# Register remote API tools into MCP instance
#############################################
def register_openapi_tools():
    global operations_info, mcp
    if mcp is None:
        logging.error("MCP server not initialized.")
        return

    openapi_url = os.environ.get("OPENAPI_URL")
    if openapi_url:
        _, server_url, operations_info = load_openapi(openapi_url)
        client = httpx.Client()
        for op_id, info in operations_info.items():
            safe_op_id = sanitize_tool_name(op_id)
            tool_function = generate_tool_function(
                operation_id=op_id,
                method=info["method"],
                path=info["path"],
                parameters=info.get("parameters", []),
                server_url=server_url,
                ops_info=operations_info,
                client=client
            )
            mcp.add_tool(tool_function, name=safe_op_id, description=info.get("summary", op_id))
        client.close()
    else:
        operations_info = {}
    mcp.add_tool(metadata_tool, name="tools_list", description="List available tools and capabilities")

#############################################
# Main entry point
#############################################
def main():
    transport = os.environ.get("TRANSPORT", "stdio")
    server_name = os.environ.get("SERVER_NAME", "openapi_proxy_server")
    
    mcp_instance = initialize_mcp(server_name)
    register_openapi_tools()
    
    if transport.lower() == "sse":
        run_sse_app(mcp_instance)
    else:
        # Default to stdio transport
        mcp_instance.run()

if __name__ == "__main__":
    main()