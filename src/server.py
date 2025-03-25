# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

import os
import sys
import json
import time
import re
import yaml
import logging
import httpx
from urllib.parse import urlparse, parse_qsl
from typing import Any, Dict, List, Optional, Tuple
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)


class MCPResource:
    def __init__(self, name: str, schema: dict, description: str):
        self.name = name
        self.schema = schema
        self.description = description
        self.uri = f"/resource/{name}"


class Prompt:
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
    if resource.endswith("ies"):
        return resource[:-3] + "y"
    elif resource.endswith("sses"):
        return resource
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
        self.api_category = None

    @staticmethod
    def sanitize_name(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]

    @classmethod
    def sanitize_tool_name(cls, name: str, server_prefix: str = None) -> str:
        if server_prefix:
            prefixed_name = f"{server_prefix}_{name}"
            return cls.sanitize_name(prefixed_name)
        return cls.sanitize_name(name)

    def sanitize_resource_name(self, name: str, server_prefix: str = None) -> str:
        if server_prefix:
            prefixed_name = f"{server_prefix}_{name}"
            return self.sanitize_name(prefixed_name)
        return self.sanitize_name(name)

    def convert_schema_to_resource(self, schema: Dict[str, Any]) -> Dict[str, Any]:
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
            return {}, "", {}
        if not isinstance(spec, dict) or "paths" not in spec or "info" not in spec:
            logging.error("Invalid OpenAPI spec: Missing required properties")
            return {}, "", {}
        
        # Set API category from the spec info
        if "info" in spec:
            self.api_category = spec["info"].get("title", "API").split()[0]
            
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
                    "responseSchema": response_schema,
                    "tags": op.get("tags", [])
                }
        logging.info("Loaded %d operations from OpenAPI spec.", len(ops_info))
        return spec, server_url, ops_info

    def get_tool_metadata(self, ops: Dict[str, Any]) -> Dict[str, Any]:
        tools = []
        for op_id, info in ops.items():
            prefixed_op_id = f"{self.server_name}_{op_id}"
            safe_id = self.sanitize_tool_name(prefixed_op_id)
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
                
            # Add tags from original operation plus our server name
            tags = info.get("tags", [])
            if self.api_category:
                tags.append(self.api_category)
            tags.append(self.server_name)
            tags.append("openapi")
            
            # Enhanced description with server context
            enhanced_description = f"[{self.server_name}] {info.get('summary', op_id)}"
            
            tool_meta = {
                "name": safe_id,
                "description": enhanced_description,
                "inputSchema": schema,
                "parameters": parameters_info,
                "tags": tags,
                "serverInfo": {
                    "name": self.server_name
                }
            }
            if info.get("responseSchema"):
                tool_meta["responseSchema"] = info["responseSchema"]
            tools.append(tool_meta)
        return {"tools": tools}

    def parse_kwargs_string(self, s: str) -> Dict[str, Any]:
        """
        Parse a kwargs string. This function automatically strips any surrounding backticks or code fences.
        It supports:
          - Standard JSON (with numbers as numbers or strings)
          - Double-escaped JSON strings (e.g. \\" instead of ")
          - Query string formats using '&'
          - Comma-separated key/value pairs (e.g. "lat=63.1115,lon=7.7327")
        """
        s = s.strip()
        s = re.sub(r"^`+|`+$", "", s)  # Remove surrounding backticks
        s = re.sub(r"^```+|```+$", "", s)  # Remove surrounding triple backticks if present
        if s.startswith('?'):
            s = s[1:]
            
        # Log the input string for debugging
        logging.debug("Parsing kwargs string: %s", s)
        
        # Try standard JSON parsing first
        try:
            parsed = json.loads(s)
            if isinstance(parsed, dict):
                logging.debug("Standard JSON parsing succeeded")
                return parsed
        except Exception as e:
            logging.debug("Standard JSON parsing failed: %s", e)
        
        # Try with simple unescaping
        try:
            s_unescaped = s.replace('\\"', '"')
            parsed = json.loads(s_unescaped)
            if isinstance(parsed, dict):
                logging.debug("JSON parsing with simple unescaping succeeded")
                return parsed
        except Exception as e:
            logging.debug("JSON parsing with simple unescaping failed: %s", e)
            
        # Try with additional unescaping for backslashes
        try:
            s_double_unescaped = s.replace('\\\\', '\\')
            parsed = json.loads(s_double_unescaped)
            if isinstance(parsed, dict):
                logging.debug("JSON parsing with double unescaping succeeded")
                return parsed
        except Exception as e:
            logging.debug("JSON parsing with double unescaping failed: %s", e)
            
        # Try with both types of unescaping
        try:
            s_fully_unescaped = s.replace('\\\\', '\\').replace('\\"', '"')
            parsed = json.loads(s_fully_unescaped)
            if isinstance(parsed, dict):
                logging.debug("JSON parsing with full unescaping succeeded")
                return parsed
        except Exception as e:
            logging.debug("JSON parsing with full unescaping failed: %s", e)
            
        # Extra attempt for the specific case where we have JSON inside a string
        # For example: {"lat":59.83,"lon":10.43} or {"lat":"59.83","lon":"10.43"}
        json_pattern = r'(\{.*?\})'
        json_matches = re.findall(json_pattern, s)
        if json_matches:
            for json_str in json_matches:
                try:
                    parsed = json.loads(json_str)
                    if isinstance(parsed, dict):
                        logging.debug("Extracted JSON substring parsing succeeded")
                        return parsed
                except Exception:
                    continue
                    
        # Try standard query string parsing (expects '&' delimiter)
        parsed_qsl = dict(parse_qsl(s))
        if parsed_qsl:
            logging.debug("Query string parsing succeeded")
            return parsed_qsl
            
        # Fallback: if the string contains commas (but no '&'), split on commas manually.
        if ',' in s and '&' not in s:
            result = {}
            pairs = s.split(',')
            for pair in pairs:
                pair = pair.strip()
                if not pair:
                    continue
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    # Try to convert values to appropriate types
                    try:
                        # Try to convert to number if appropriate
                        float_val = float(value.strip())
                        # Check if it's an integer
                        if float_val.is_integer():
                            result[key.strip()] = int(float_val)
                        else:
                            result[key.strip()] = float_val
                    except ValueError:
                        result[key.strip()] = value.strip()
            if result:
                logging.debug("Comma-separated parsing succeeded")
                return result
                
        logging.warning("All parsing methods failed for string: %s", s)
        return {}

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
        if 'kwargs' in kwargs:
            if isinstance(kwargs['kwargs'], str):
                raw = kwargs.pop('kwargs')
                raw = re.sub(r"^`+|`+$", "", raw)
                logging.info("Parsing kwargs string: %s", raw)
                parsed_kwargs = self.parse_kwargs_string(raw)
                if not parsed_kwargs:
                    logging.warning("Failed to parse kwargs string, returning error")
                    return None, {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {
                            "code": -32602, 
                            "message": f"Could not parse kwargs string: '{raw}'. Please check format."
                        }
                    }
                kwargs.update(parsed_kwargs)
                logging.info("Parsed kwargs: %s", kwargs)
            elif isinstance(kwargs['kwargs'], dict):
                # If kwargs is already a dict, just use it directly
                kwargs.update(kwargs.pop('kwargs'))
                logging.info("Using provided kwargs dict: %s", kwargs)
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
        server_description = self.openapi_spec.get("info", {}).get("description", f"OpenAPI Proxy for {self.server_name}")
        api_title = self.openapi_spec.get("info", {}).get("title", "API")
        
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {
                    "name": self.server_name, 
                    "version": "1.0.0",
                    "description": f"OpenAPI Proxy for {api_title}: {server_description}",
                    "category": self.api_category or "API Integration",
                    "tags": ["openapi", "api", self.server_name, self.api_category] if self.api_category else ["openapi", "api", self.server_name]
                }
            }
        }

    def tools_list_tool(self, req_id: Any = None):
        tool_list = [data["metadata"] for data in self.registered_tools.values()]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tool_list}}

    def tools_call_tool(self, req_id: Any = None, name: str = None, arguments: Optional[Dict[str, Any]] = None):
        if not name:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Missing tool name"}}
            
        # Handle case where user forgot the server prefix
        if name not in self.registered_tools:
            prefixed_name = f"{self.server_name}_{name}"
            if prefixed_name in self.registered_tools:
                name = prefixed_name
            else:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool '{name}' not found. Did you mean '{self.server_name}_{name}'?"}}
                
        try:
            func = self.registered_tools[name]["function"]
            return func(req_id=req_id, **(arguments or {}))
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": str(e)}}

    def add_tool(self, name: str, func: Any, description: str, metadata: Optional[Dict[str, Any]] = None):
        # Add server name as prefix
        prefixed_name = f"{self.server_name}_{name}"
        safe_name = self.sanitize_tool_name(prefixed_name)
        
        # Enhance description with server context
        enhanced_description = f"[{self.server_name}] {description}"
        
        if metadata is None:
            metadata = {
                "name": safe_name, 
                "description": enhanced_description,
                "tags": ["openapi", "api", self.server_name],
                "serverInfo": {"name": self.server_name}
            }
        else:
            metadata["name"] = safe_name
            metadata["description"] = enhanced_description
            # Add tags if not present
            if "tags" not in metadata:
                metadata["tags"] = ["openapi", "api", self.server_name]
            # Add server info
            metadata["serverInfo"] = {"name": self.server_name}
            
        self.registered_tools[safe_name] = {"function": func, "metadata": metadata}
        self.mcp.add_tool(func, name=safe_name, description=enhanced_description)

    def register_openapi_tools(self):
        openapi_url = os.environ.get("OPENAPI_URL")
        if openapi_url:
            try:
                logging.info("Loading OpenAPI spec from: %s", openapi_url)
                spec, server_url, ops_info = self.load_openapi(openapi_url)
            except Exception as e:
                logging.error("Failed to load OpenAPI spec from %s: %s", openapi_url, e)
                spec, server_url, ops_info = {}, "", {}
            self.openapi_spec = spec
            self.operations_info = ops_info
            
            # Log OpenAPI info
            api_title = spec.get("info", {}).get("title", "Unknown API")
            api_version = spec.get("info", {}).get("version", "Unknown version")
            logging.info("Loaded API: %s (version: %s)", api_title, api_version)
            
            # Register resources and count them
            resource_count = self.register_openapi_resources()
            logging.info("Registered %d resources from OpenAPI spec", resource_count)
            
            # Register tools and count successful registrations
            tool_count = 0
            for op_id, info in ops_info.items():
                try:
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
                    self.add_tool(op_id, func, info.get("summary", op_id), tool_meta)
                    tool_count += 1
                except Exception as e:
                    logging.error("Failed to register tool for operation %s: %s", op_id, e)
                    
            logging.info("Successfully registered %d/%d API tools", tool_count, len(ops_info))
        else:
            logging.warning("No OPENAPI_URL provided, skipping API tools registration")
            
        # Register standard MCP tools
        self.add_tool("initialize", self.initialize_tool, "Initialize MCP server.")
        self.add_tool("tools_list", self.tools_list_tool, "List available tools with extended metadata.")
        self.add_tool("tools_call", self.tools_call_tool, "Call a tool by name with provided arguments.")
        logging.info("Registered 3 standard MCP tools")

    def register_openapi_resources(self) -> int:
        schemas = self.openapi_spec.get("components", {}).get("schemas", {})
        resource_count = 0
        
        for schema_name, schema in schemas.items():
            # Prefix resource name with server name
            prefixed_name = f"{self.server_name}_{schema_name}"
            safe_name = self.sanitize_resource_name(prefixed_name)
            
            resource_schema = self.convert_schema_to_resource(schema)
            resource_description = f"[{self.server_name}] {schema.get('description', f'Resource for {schema_name}')}"
            
            resource_obj = MCPResource(
                name=safe_name,
                schema=resource_schema,
                description=resource_description
            )
            self.mcp.add_resource(resource_obj)
            self.registered_resources[safe_name] = {
                "schema": resource_schema,
                "metadata": {
                    "name": safe_name, 
                    "description": resource_description,
                    "serverInfo": {"name": self.server_name},
                    "tags": ["resource", self.server_name, self.api_category] if self.api_category else ["resource", self.server_name]
                }
            }
            resource_count += 1
            
        return resource_count

    def generate_api_prompts(self) -> int:
        info = self.openapi_spec.get("info", {})
        api_title = info.get('title', 'API')
        general_prompt = f"""
# {self.server_name} - API Usage Guide for {api_title}

This API provides the following capabilities:
"""
        for path, methods in self.openapi_spec.get("paths", {}).items():
            for method, details in methods.items():
                if method.lower() in {"get", "post", "put", "delete", "patch"}:
                    raw_tool_name = details.get("operationId") or f"{method}_{path}"
                    tool_name = f"{self.server_name}_{raw_tool_name}"
                    general_prompt += f"\n## {tool_name}\n"
                    general_prompt += f"- Path: `{path}` (HTTP {method.upper()})\n"
                    general_prompt += f"- Description: {details.get('description') or details.get('summary', 'No description')}\n"
                    if details.get("parameters"):
                        general_prompt += "- Parameters:\n"
                        for param in details.get("parameters", []):
                            required = "Required" if param.get("required") else "Optional"
                            general_prompt += f"  - `{param.get('name')}` ({param.get('in')}): {param.get('description', 'No description')} [{required}]\n"
        prompt_name = f"{self.server_name}_api_general_usage"
        prompt_description = f"[{self.server_name}] General guidance for using {api_title} API"
        prompt = Prompt(prompt_name, general_prompt, prompt_description)
        self.mcp.add_prompt(prompt)
        
        return 1  # Return number of prompts created

    def identify_crud_operations(self) -> Dict[str, Dict[str, str]]:
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

    def generate_example_prompts(self) -> int:
        crud_ops = self.identify_crud_operations()
        prompt_count = 0
        
        for resource, operations in crud_ops.items():
            example_prompt = f"""
# {self.server_name} - Examples for working with {resource}

Common scenarios for handling {resource} resources:
"""
            if "list" in operations:
                prefixed_op = f"{self.server_name}_{operations['list']}"
                example_prompt += f"""
## Listing {resource} resources

To list all {resource} resources:
```
{{{{tool.{prefixed_op}()}}}}
```
"""
            if "get" in operations:
                prefixed_op = f"{self.server_name}_{operations['get']}"
                example_prompt += f"""
## Getting a specific {resource}

To retrieve a specific {resource} by ID:
```
{{{{tool.{prefixed_op}(id="example-id")}}}}
```
"""
            if "create" in operations:
                prefixed_op = f"{self.server_name}_{operations['create']}"
                example_prompt += f"""
## Creating a new {resource}

To create a new {resource}:
```
{{{{tool.{prefixed_op}(
    name="Example name",
    description="Example description"
    # Add other required fields
)}}}}
```
"""
            prompt_name = f"{self.server_name}_{resource}_examples"
            prompt_description = f"[{self.server_name}] Example usage patterns for {resource} resources"
            prompt = Prompt(prompt_name, example_prompt, prompt_description)
            self.mcp.add_prompt(prompt)
            prompt_count += 1
            
        return prompt_count

    def run(self):
        self.mcp.run(transport="stdio")


def main():
    openapi_url = os.environ.get("OPENAPI_URL")
    if not openapi_url:
        print("ERROR: Environment variable OPENAPI_URL is required to start the server.", file=sys.stderr)
        sys.exit(1)

    server_name = os.environ.get("SERVER_NAME", "openapi_proxy_server")
    logging.info("Starting OpenAPI-MCP server with name: %s", server_name)
    logging.info("OpenAPI URL: %s", openapi_url)
    
    start_time = time.time()
    server = MCPServer(server_name)
    server.register_openapi_tools()
    
    # Generate prompts and log counts
    general_prompts = server.generate_api_prompts()
    example_prompts = server.generate_example_prompts()
    total_prompts = general_prompts + example_prompts
    logging.info("Generated %d prompts (%d general, %d example prompts)", 
                 total_prompts, general_prompts, example_prompts)
    
    # Count registered tools
    total_tools = len(server.registered_tools)
    api_tools = total_tools - 3  # Subtract the 3 standard tools
    logging.info("Total registered tools: %d (API tools: %d, Standard tools: 3)", 
                 total_tools, api_tools)
    
    # Count registered resources
    total_resources = len(server.registered_resources)
    logging.info("Total registered resources: %d", total_resources)
    
    # Log summary information
    setup_time = time.time() - start_time
    logging.info("Server setup completed in %.2f seconds", setup_time)
    logging.info("Server %s ready with %d tools, %d resources, and %d prompts", 
                 server_name, total_tools, total_resources, total_prompts)
    
    logging.info("Starting MCP server...")
    server.run()


if __name__ == "__main__":
    main()
