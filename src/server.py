# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord

import os, sys, json, time, re, yaml, logging, httpx
from urllib.parse import urlparse, parse_qsl
from typing import Any, Dict, List, Optional, Tuple
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)

class MCPResource:
    def __init__(self, name: str, schema: dict, description: str):
        self.name = name
        self.schema = schema
        self.description = description
        # Set the URI as expected by FastMCP resource manager
        self.uri = f"/resource/{name}"

class Prompt:
    # Simple Prompt class to work with FastMCP.add_prompt
    def __init__(self, name: str, content: str, description: str = ""):
        self.name = name
        self.content = content
        self.description = description

class OAuthCache:
    def __init__(self):
        self.token = None
        self.expiry = 0

    def get_token(self) -> Optional[str]:
        if self.token and time.time() < self.expiry:
            return self.token
        return None

    def set_token(self, token: str, expires_in: int = 3600):
        self.token = token
        self.expiry = time.time() + expires_in

def singularize_resource(resource: str) -> str:
    # Simple singularization logic for common cases.
    if resource.endswith("ies"):
        return resource[:-3] + "y"
    elif resource.endswith("sses"):
        return resource  # e.g. "processes" remains unchanged
    elif resource.endswith("s") and not resource.endswith("ss"):
        return resource[:-1]
    return resource

class MCPServer:
    def __init__(self, server_name: str = "openapi_proxy_server"):
        self.server_name = server_name
        self.mcp = FastMCP(server_name)
        self.oauth_cache = OAuthCache()
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.registered_resources: Dict[str, Dict[str, Any]] = {}
        self.operations_info: Dict[str, Dict[str, Any]] = {}
        self.openapi_spec: Dict[str, Any] = {}

    @staticmethod
    def sanitize_name(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]

    @classmethod
    def sanitize_tool_name(cls, name: str) -> str:
        return cls.sanitize_name(name)

    def sanitize_resource_name(self, name: str) -> str:
        return self.sanitize_tool_name(name)

    def convert_schema_to_resource(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Converts an OpenAPI schema to an MCP resource schema."""
        if not schema:
            return {"type": "object", "properties": {}}

        properties = {}
        required = schema.get("required", [])
        for prop_name, prop_schema in schema.get("properties", {}).items():
            prop_type = prop_schema.get("type", "string")
            if prop_type == "integer":
                properties[prop_name] = {
                    "type": "number",
                    "description": prop_schema.get("description", "")
                }
            elif prop_type == "array":
                items_type = self.convert_schema_to_resource(prop_schema.get("items", {}))
                properties[prop_name] = {
                    "type": "array",
                    "items": items_type,
                    "description": prop_schema.get("description", "")
                }
            elif prop_type == "object":
                nested_schema = self.convert_schema_to_resource(prop_schema)
                nested_schema["description"] = prop_schema.get("description", "")
                properties[prop_name] = nested_schema
            else:
                properties[prop_name] = {
                    "type": prop_type,
                    "description": prop_schema.get("description", "")
                }
        resource_schema = {"type": "object", "properties": properties}
        if required:
            resource_schema["required"] = required
        return resource_schema

    def get_oauth_access_token(self) -> Optional[str]:
        token = self.oauth_cache.get_token()
        if token:
            return token
        cid = os.environ.get("OAUTH_CLIENT_ID")
        csec = os.environ.get("OAUTH_CLIENT_SECRET")
        token_url = os.environ.get("OAUTH_TOKEN_URL")
        scope = os.environ.get("OAUTH_SCOPE", "api")
        if cid and csec and token_url:
            try:
                resp = httpx.post(
                    token_url,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "grant_type": "client_credentials",
                        "client_id": cid,
                        "client_secret": csec,
                        "scope": scope
                    }
                )
                resp.raise_for_status()
                token_data = resp.json()
                access_token = token_data.get("access_token")
                expires = token_data.get("expires_in", 3600)
                self.oauth_cache.set_token(access_token, expires)
                logging.info("OAuth token obtained")
                return access_token
            except Exception as e:
                logging.error("Error obtaining OAuth token: %s", e)
                sys.exit(1)
        logging.info("No OAuth credentials; proceeding without token.")
        return None

    def load_openapi(self, openapi_url: str) -> Tuple[Dict[str, Any], str, Dict[str, Dict[str, Any]]]:
        try:
            resp = httpx.get(openapi_url)
            resp.raise_for_status()
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                spec = resp.json()
            else:
                spec = yaml.safe_load(resp.text)
        except Exception as e:
            logging.error("Could not load OpenAPI spec: %s", e)
            sys.exit(1)
        if not isinstance(spec, dict) or "paths" not in spec or "info" not in spec:
            logging.error("Invalid OpenAPI spec: Missing required properties")
            sys.exit(1)
        servers = spec.get("servers")
        raw_url = ""
        parsed = urlparse(openapi_url)
        if isinstance(servers, list) and servers:
            raw_url = servers[0].get("url", "")
        elif isinstance(servers, dict):
            raw_url = servers.get("url", "")
        if not raw_url:
            base = parsed.path.rsplit('/', 1)[0]
            raw_url = f"{parsed.scheme}://{parsed.netloc}{base}"
        if raw_url.startswith("/"):
            server_url = f"{parsed.scheme}://{parsed.netloc}{raw_url}"
        elif not raw_url.startswith(("http://", "https://")):
            server_url = f"https://{raw_url}"
        else:
            server_url = raw_url

        ops_info = {}
        for path, path_item in spec.get("paths", {}).items():
            for method, op in path_item.items():
                if method.lower() not in {"get", "post", "put", "delete", "patch", "head", "options"}:
                    continue

                # Handle requestBody explicitly for POST/PUT operations
                if "requestBody" in op:
                    req_body = op["requestBody"]
                    body_schema = {}
                    if "content" in req_body and "application/json" in req_body["content"]:
                        body_schema = req_body["content"]["application/json"].get("schema", {})
                    op.setdefault("parameters", []).append({
                        "name": "body",
                        "in": "body",
                        "required": req_body.get("required", False),
                        "schema": body_schema,
                        "description": "Request body"
                    })

                # Map response schema if available (200 response)
                response_schema = None
                if "responses" in op and "200" in op["responses"]:
                    resp200 = op["responses"]["200"]
                    if "content" in resp200 and "application/json" in resp200["content"]:
                        response_schema = resp200["content"]["application/json"].get("schema", None)

                raw_op_id = op.get("operationId") or f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                sanitized_op_id = self.sanitize_tool_name(raw_op_id)
                summary = op.get("description") or op.get("summary") or sanitized_op_id
                ops_info[sanitized_op_id] = {
                    "summary": summary,
                    "parameters": op.get("parameters", []),
                    "path": path,
                    "method": method.upper(),
                    "responseSchema": response_schema
                }
        logging.info("Loaded %d operations from OpenAPI spec.", len(ops_info))
        return spec, server_url, ops_info

    def get_tool_metadata(self, ops: Dict[str, Any]) -> Dict[str, Any]:
        tools = []
        for op_id, info in ops.items():
            safe_id = self.sanitize_tool_name(op_id)
            properties = {}
            required = []
            parameters_info = []
            for param in info.get("parameters", []):
                name = param.get("name")
                p_schema = param.get("schema", {})
                p_type = p_schema.get("type", "string")
                desc = param.get("description", f"Type: {p_type}")
                properties[name] = {"type": p_type, "description": desc}
                parameters_info.append({
                    "name": name,
                    "in": param.get("in", "query"),
                    "required": param.get("required", False),
                    "type": p_type,
                    "description": desc
                })
                if param.get("required", False):
                    required.append(name)
            schema = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            tool_meta = {
                "name": safe_id,
                "description": info.get("summary", op_id),
                "inputSchema": schema,
                "parameters": parameters_info
            }
            # Include responseSchema if available
            if info.get("responseSchema"):
                tool_meta["responseSchema"] = info["responseSchema"]
            tools.append(tool_meta)
        return {"tools": tools}

    def parse_kwargs_string(self, s: str) -> Dict[str, Any]:
        """
        Attempts to parse the kwargs string as JSON; falls back to query string parsing.
        Supports strings starting with a '?' and various JSON variations.
        """
        s = s.strip()
        if s.startswith('?'):
            s = s[1:]
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            logging.debug("JSON parsing failed: %s", e)
        try:
            s_unescaped = s.replace('\\"', '"')
            parsed = json.loads(s_unescaped)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            logging.debug("JSON parsing with unescaping failed: %s", e)
        return dict(parse_qsl(s))

    def _prepare_request(
        self,
        req_id: Any,
        kwargs: Dict[str, Any],
        parameters: List[Dict[str, Any]],
        path: str,
        server_url: str,
        op_id: str,
        ops: Dict[str, Any]
    ) -> Tuple[Optional[Tuple[str, Dict, Dict, Any, bool]], Optional[Dict]]:
        if 'kwargs' in kwargs and isinstance(kwargs['kwargs'], str):
            raw = kwargs.pop('kwargs').strip('`')
            logging.info("Parsing kwargs string: %s", raw)
            parsed_kwargs = self.parse_kwargs_string(raw)
            kwargs.update(parsed_kwargs)
            logging.info("Parsed kwargs: %s", kwargs)
        expected = [p["name"] for p in parameters if p.get("required", False)]
        logging.info("Expected required parameters: %s", expected)
        logging.info("Available parameters: %s", list(kwargs.keys()))
        missing = [name for name in expected if name not in kwargs]
        if missing:
            return None, {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"help": f"Missing parameters: {missing}"}
            }
        dry_run = kwargs.pop("dry_run", False)
        req_params, req_headers, req_body = {}, {}, None
        for param in parameters:
            name, loc = param["name"], param.get("in", "query")
            if name in kwargs:
                try:
                    p_schema = param.get("schema", {})
                    p_type = p_schema.get("type", "string")
                    val = kwargs[name]
                    if p_type == "integer":
                        val = int(val)
                    elif p_type == "number":
                        val = float(val)
                    elif p_type == "boolean":
                        val = str(val).lower() in {"true", "1", "yes", "y"}
                except Exception as e:
                    return None, {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32602, "message": f"Parameter '{name}' conversion error: {e}"}
                    }
                if loc == "path":
                    path = path.replace(f"{{{name}}}", str(val))
                elif loc == "query":
                    req_params[name] = val
                elif loc == "header":
                    req_headers[name] = val
                elif loc == "body":
                    req_body = val
        if (token := self.get_oauth_access_token()):
            req_headers["Authorization"] = f"Bearer {token}"
        req_headers.setdefault("User-Agent", "OpenAPI-MCP/1.0")
        full_url = server_url.rstrip("/") + "/" + path.lstrip("/")
        return (full_url, req_params, req_headers, req_body, dry_run), None

    def generate_tool_function(
        self,
        op_id: str,
        method: str,
        path: str,
        parameters: List[Dict[str, Any]],
        server_url: str,
        ops: Dict[str, Any],
        client: Any
    ):
        def build_response(req_id, result=None, error=None):
            if error:
                return {"jsonrpc": "2.0", "id": req_id, "error": error}
            return {"jsonrpc": "2.0", "id": req_id, "result": result}
        def tool_func(req_id: Any = None, **kwargs):
            prep, err = self._prepare_request(req_id, kwargs, parameters, path, server_url, op_id, ops)
            if err:
                return err
            full_url, req_params, req_headers, req_body, dry_run = prep
            if dry_run:
                return build_response(req_id, result={
                    "dry_run": True,
                    "request": {
                        "url": full_url,
                        "method": method,
                        "headers": req_headers,
                        "params": req_params,
                        "body": req_body
                    }
                })
            try:
                resp = client.request(
                    method=method,
                    url=full_url,
                    params=req_params,
                    headers=req_headers,
                    json=req_body if req_body else None
                )
                resp.raise_for_status()
                try:
                    data = resp.json()
                except Exception:
                    data = {"raw_response": resp.text}
                return build_response(req_id, result={"data": data})
            except Exception as e:
                return build_response(req_id, error={"code": -32603, "message": str(e)})
        return tool_func

    def initialize_tool(self, req_id: Any = None, **kwargs):
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": self.server_name, "version": "1.0.0"}
            }
        }

    def tools_list_tool(self, req_id: Any = None):
        tool_list = [data["metadata"] for data in self.registered_tools.values()]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tool_list}}

    def tools_call_tool(self, req_id: Any = None, name: str = None, arguments: Optional[Dict[str, Any]] = None):
        if not name:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Missing tool name"}}
        if name not in self.registered_tools:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool '{name}' not found"}}
        try:
            func = self.registered_tools[name]["function"]
            return func(req_id=req_id, **(arguments or {}))
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

    def add_tool(self, name: str, func: Any, description: str, metadata: Optional[Dict[str, Any]] = None):
        safe_name = self.sanitize_tool_name(name)
        if metadata is None:
            metadata = {"name": safe_name, "description": description}
        self.registered_tools[safe_name] = {"function": func, "metadata": metadata}
        self.mcp.add_tool(func, name=safe_name, description=description)

    def register_openapi_tools(self):
        openapi_url = os.environ.get("OPENAPI_URL")
        if openapi_url:
            spec, server_url, ops_info = self.load_openapi(openapi_url)
            self.openapi_spec = spec
            self.operations_info = ops_info
            self.register_openapi_resources()
            for op_id, info in ops_info.items():
                client = httpx.Client()
                tool_meta = self.get_tool_metadata({op_id: info})["tools"][0]
                func = self.generate_tool_function(
                    op_id,
                    info["method"],
                    info["path"],
                    info.get("parameters", []),
                    server_url,
                    ops_info,
                    client
                )
                metadata = {
                    "name": op_id,
                    "description": info.get("summary", op_id),
                    "inputSchema": tool_meta["inputSchema"],
                    "parameters": tool_meta.get("parameters")
                }
                if "responseSchema" in tool_meta:
                    metadata["responseSchema"] = tool_meta["responseSchema"]
                self.add_tool(op_id, func, metadata["description"], metadata)
        self.add_tool("initialize", self.initialize_tool, "Initialize MCP server.")
        self.add_tool("tools_list", self.tools_list_tool, "List available tools with extended metadata.")
        self.add_tool("tools_call", self.tools_call_tool, "Call a tool by name with provided arguments.")

    def register_openapi_resources(self):
        schemas = self.openapi_spec.get("components", {}).get("schemas", {})
        for schema_name, schema in schemas.items():
            safe_name = self.sanitize_resource_name(schema_name)
            resource_schema = self.convert_schema_to_resource(schema)
            resource_obj = MCPResource(
                name=safe_name,
                schema=resource_schema,
                description=schema.get("description", f"Resource for {schema_name}")
            )
            self.mcp.add_resource(resource_obj)
            self.registered_resources[safe_name] = {
                "schema": resource_schema,
                "metadata": {"name": safe_name, "description": schema.get("description", f"Resource for {schema_name}")}
            }

    def generate_api_prompts(self):
        """Generates useful prompts for the LLM based on API operations."""
        info = self.openapi_spec.get("info", {})
        general_prompt = f"""
# API Usage Guide for {info.get('title', 'API')}

This API provides the following capabilities:
"""
        for path, methods in self.openapi_spec.get("paths", {}).items():
            for method, details in methods.items():
                if method.lower() in {"get", "post", "put", "delete", "patch"}:
                    tool_name = self.sanitize_tool_name(details.get("operationId") or f"{method}_{path}")
                    general_prompt += f"\n## {tool_name}\n"
                    general_prompt += f"- Path: `{path}` (HTTP {method.upper()})\n"
                    general_prompt += f"- Description: {details.get('description') or details.get('summary', 'No description')}\n"
                    if details.get("parameters"):
                        general_prompt += "- Parameters:\n"
                        for param in details.get("parameters", []):
                            required = "Required" if param.get("required") else "Optional"
                            general_prompt += f"  - `{param.get('name')}` ({param.get('in')}): {param.get('description', 'No description')} [{required}]\n"
        prompt = Prompt("api_general_usage", general_prompt, "General guidance for using this API")
        self.mcp.add_prompt(prompt)

    def identify_crud_operations(self) -> Dict[str, Dict[str, str]]:
        """Identifies CRUD operations for resources based on API paths."""
        crud_ops = {}
        for path, methods in self.openapi_spec.get("paths", {}).items():
            path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
            if not path_parts:
                continue
            resource = singularize_resource(path_parts[-1])
            if resource not in crud_ops:
                crud_ops[resource] = {}
            for method, details in methods.items():
                op_id = self.sanitize_tool_name(details.get("operationId") or f"{method}_{path}")
                if method.lower() == "get":
                    if "{" in path and "}" in path:
                        crud_ops[resource]["get"] = op_id
                    else:
                        crud_ops[resource]["list"] = op_id
                elif method.lower() == "post":
                    crud_ops[resource]["create"] = op_id
                elif method.lower() in {"put", "patch"}:
                    crud_ops[resource]["update"] = op_id
                elif method.lower() == "delete":
                    crud_ops[resource]["delete"] = op_id
        return crud_ops

    def generate_example_prompts(self):
        """Generates example prompts for common API usage scenarios."""
        crud_ops = self.identify_crud_operations()
        for resource, operations in crud_ops.items():
            example_prompt = f"""
# Examples for working with {resource}

Here are some common scenarios for working with {resource} resources:
"""
            if "list" in operations:
                example_prompt += f"""
## Listing {resource} resources

To list all {resource} resources:
```
{{{{tool.{operations['list']}()}}}}
```
"""
            if "get" in operations:
                example_prompt += f"""
## Getting a specific {resource}

To get a specific {resource} by ID:
```
{{{{tool.{operations['get']}(id="example-id")}}}}
```
"""
            if "create" in operations:
                example_prompt += f"""
## Creating a new {resource}

To create a new {resource}:
```
{{{{tool.{operations['create']}(
    name="Example name",
    description="Example description"
    # Add other required fields
)}}}}
```
"""
            prompt = Prompt(f"{resource}_examples", example_prompt, f"Example usage patterns for {resource} resources")
            self.mcp.add_prompt(prompt)

    def run(self):
        self.mcp.run(transport="stdio")

def main():
    server_name = os.environ.get("SERVER_NAME", "openapi_proxy_server")
    server = MCPServer(server_name)
    server.register_openapi_tools()
    server.generate_api_prompts()
    server.generate_example_prompts()
    server.run()

if __name__ == "__main__":
    main()

