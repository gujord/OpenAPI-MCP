import os, sys, json, time, re, yaml, logging, httpx
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Tuple
from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)

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

class MCPServer:
    def __init__(self, server_name: str = "openapi_proxy_server"):
        self.server_name = server_name
        self.mcp = FastMCP(server_name)
        self.oauth_cache = OAuthCache()
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.operations_info: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def sanitize_tool_name(name: str) -> str:
        # Ensure tool names conform to ^[a-zA-Z0-9_-]{1,64}$
        # Replace invalid chars with underscore, then truncate to 64 chars.
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]

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
        if isinstance(servers, list) and servers:
            raw_url = servers[0].get("url", "")
        elif isinstance(servers, dict):
            raw_url = servers.get("url", "")
        if not raw_url:
            parsed = urlparse(openapi_url)
            base = parsed.path.rsplit('/', 1)[0]
            raw_url = f"{parsed.scheme}://{parsed.netloc}{base}"
        else:
            parsed = urlparse(openapi_url)

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
                # Original or fallback operationId
                raw_op_id = op.get("operationId") or f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                # Sanitize to ensure it meets ^[a-zA-Z0-9_-]{1,64}$
                sanitized_op_id = self.sanitize_tool_name(raw_op_id)
                summary = op.get("description") or op.get("summary") or sanitized_op_id
                ops_info[sanitized_op_id] = {
                    "summary": summary,
                    "parameters": op.get("parameters", []),
                    "path": path,
                    "method": method.upper()
                }
        logging.info("Loaded %d operations from OpenAPI spec.", len(ops_info))
        return spec, server_url, ops_info

    def get_tool_metadata(self, ops: Dict[str, Any]) -> Dict[str, Any]:
        tools = []
        for op_id, info in ops.items():
            safe_id = self.sanitize_tool_name(op_id)
            properties = {}
            required = []
            for param in info.get("parameters", []):
                name = param.get("name")
                p_schema = param.get("schema", {})
                p_type = p_schema.get("type", "string")
                desc = param.get("description", f"Type: {p_type}")
                properties[name] = {"type": p_type, "description": desc}
                if param.get("required", False):
                    required.append(name)
            schema = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
            tools.append({
                "name": safe_id,
                "description": info.get("summary", op_id),
                "inputSchema": schema
            })
        return {"tools": tools}

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
        local_path = path
        missing = [p["name"] for p in parameters if p.get("required", False) and p["name"] not in kwargs]
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
                    local_path = local_path.replace(f"{{{name}}}", str(val))
                elif loc == "query":
                    req_params[name] = val
                elif loc == "header":
                    req_headers[name] = val
                elif loc == "body":
                    req_body = val

        if (token := self.get_oauth_access_token()):
            req_headers["Authorization"] = f"Bearer {token}"
        req_headers.setdefault("User-Agent", "OpenAPI-MCP/1.0")
        full_url = server_url.rstrip("/") + "/" + local_path.lstrip("/")
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
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": "Missing tool name"}
            }
        if name not in self.registered_tools:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Tool '{name}' not found"}
            }
        try:
            func = self.registered_tools[name]["function"]
            ret = func(req_id=req_id, **(arguments or {}))
            return ret
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            }

    def register_openapi_tools(self):
        openapi_url = os.environ.get("OPENAPI_URL")
        if openapi_url:
            _, server_url, ops_info = self.load_openapi(openapi_url)
            self.operations_info = ops_info
            for op_id, info in ops_info.items():
                func = self.generate_tool_function(
                    op_id,
                    info["method"],
                    info["path"],
                    info.get("parameters", []),
                    server_url,
                    ops_info,
                    httpx.Client()
                )
                metadata = {
                    "name": op_id,
                    "description": info.get("summary", op_id),
                    "inputSchema": self.get_tool_metadata({op_id: info})["tools"][0]["inputSchema"]
                }
                self.registered_tools[op_id] = {"function": func, "metadata": metadata}

        # Use sanitized names for built-in tools so they don't violate ^[a-zA-Z0-9_-]{1,64}$
        safe_init = self.sanitize_tool_name("initialize")
        self.registered_tools[safe_init] = {
            "function": self.initialize_tool,
            "metadata": {
                "name": safe_init,
                "description": "Initialize MCP server."
            }
        }

        safe_tools_list = self.sanitize_tool_name("tools_list")
        self.registered_tools[safe_tools_list] = {
            "function": self.tools_list_tool,
            "metadata": {
                "name": safe_tools_list,
                "description": "List available tools."
            }
        }

        safe_tools_call = self.sanitize_tool_name("tools_call")
        self.registered_tools[safe_tools_call] = {
            "function": self.tools_call_tool,
            "metadata": {
                "name": safe_tools_call,
                "description": "Call a tool."
            }
        }

        # Now add all to the MCP instance
        for name, data in self.registered_tools.items():
            # Ensure final name is sanitized (some might already be sanitized from load_openapi)
            safe_name = self.sanitize_tool_name(name)
            self.mcp.add_tool(
                data["function"],
                name=safe_name,
                description=data["metadata"].get("description", "")
            )

    def run(self):
        self.mcp.run(transport="stdio")

def main():
    server_name = os.environ.get("SERVER_NAME", "openapi_proxy_server")
    server = MCPServer(server_name)
    server.register_openapi_tools()
    server.run()

if __name__ == "__main__":
    main()
