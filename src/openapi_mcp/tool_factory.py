# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

__all__ = ["ToolMetadataBuilder", "ToolFunctionFactory"]

import logging
import httpx
from typing import Dict, Any, List, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    try:
        from .request_handler import RequestHandler
    except ImportError:
        from request_handler import RequestHandler


class ToolMetadataBuilder:
    """Builds MCP tool metadata from OpenAPI operations."""
    
    def __init__(self, server_name: str, api_category: Optional[str] = None):
        self.server_name = server_name
        self.api_category = api_category

    def build_tool_metadata(self, operations: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build tool metadata for all operations."""
        tools = []
        
        for op_id, info in operations.items():
            prefixed_op_id = f"{self.server_name}_{op_id}"
            
            # Build parameter schema
            properties, required, parameters_info = self._build_parameter_schema(info.get("parameters", []))
            
            schema = {"type": "object", "properties": properties}
            if required:
                schema["required"] = required
                
            # Build tags
            tags = self._build_tags(info.get("tags", []))
            
            # Enhanced description with server context
            enhanced_description = f"[{self.server_name}] {info.get('summary', op_id)}"
            
            tool_meta = {
                "name": prefixed_op_id,
                "description": enhanced_description,
                "inputSchema": schema,
                "parameters": parameters_info,
                "tags": tags,
                "serverInfo": {"name": self.server_name}
            }
            
            if info.get("responseSchema"):
                tool_meta["responseSchema"] = info["responseSchema"]
                
            tools.append(tool_meta)
            
        return tools

    def _build_parameter_schema(self, parameters: List[Dict[str, Any]]) -> tuple:
        """Build parameter schema and metadata."""
        properties = {}
        required = []
        parameters_info = []
        
        for param in parameters:
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
                
        return properties, required, parameters_info

    def _build_tags(self, operation_tags: List[str]) -> List[str]:
        """Build tags for the tool."""
        tags = operation_tags.copy()
        
        if self.api_category:
            tags.append(self.api_category)
            
        tags.extend([self.server_name, "openapi"])
        return tags


class ToolFunctionFactory:
    """Creates executable tool functions from OpenAPI operations."""
    
    def __init__(self, request_handler: "RequestHandler", server_url: str):
        self.request_handler = request_handler
        self.server_url = server_url

    def create_tool_function(
        self,
        op_id: str,
        method: str,
        path: str,
        parameters: List[Dict[str, Any]]
    ) -> Callable:
        """Create an executable tool function for an OpenAPI operation."""
        
        def build_response(req_id, result=None, error=None):
            """Build JSON-RPC response."""
            if error:
                return {"jsonrpc": "2.0", "id": req_id, "error": error}
            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        def tool_function(req_id: Any = None, **kwargs):
            """The actual tool function that will be called."""
            try:
                # Prepare the request
                request_data, error = self.request_handler.prepare_request(
                    req_id, kwargs, parameters, path, self.server_url, op_id
                )
                
                if error:
                    return error
                    
                full_url, req_params, req_headers, req_body, dry_run = request_data
                
                # Handle dry run
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
                
                # Execute the actual request
                return self._execute_request(
                    req_id, method, full_url, req_params, req_headers, req_body
                )
                
            except Exception as e:
                logging.error("Unexpected error in tool function %s: %s", op_id, e)
                return build_response(req_id, error={"code": -32603, "message": str(e)})
                
        return tool_function

    def _execute_request(
        self, 
        req_id: Any, 
        method: str, 
        url: str, 
        params: Dict[str, Any], 
        headers: Dict[str, str], 
        body: Any
    ) -> Dict[str, Any]:
        """Execute HTTP request and return response."""
        try:
            with httpx.Client() as client:
                response = client.request(
                    method=method,
                    url=url,
                    params=params,
                    headers=headers,
                    json=body if body else None
                )
                response.raise_for_status()
                
                # Try to parse JSON response
                try:
                    data = response.json()
                except Exception:
                    data = {"raw_response": response.text}
                    
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {"data": data}
                }
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": error_msg}
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32603, "message": str(e)}
            }