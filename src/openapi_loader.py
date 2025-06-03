# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

import logging
import yaml
import httpx
from urllib.parse import urlparse
from typing import Dict, Any, Tuple, List
try:
    from .exceptions import OpenAPIError
except ImportError:
    from exceptions import OpenAPIError


class OpenAPILoader:
    """Handles loading and parsing of OpenAPI specifications."""
    
    @staticmethod
    def load_spec(openapi_url: str) -> Dict[str, Any]:
        """Load OpenAPI spec from URL."""
        try:
            response = httpx.get(openapi_url)
            response.raise_for_status()
            
            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith("application/json"):
                spec = response.json()
            else:
                spec = yaml.safe_load(response.text)
                
        except httpx.HTTPStatusError as e:
            raise OpenAPIError(f"Failed to fetch OpenAPI spec: {e.response.status_code} {e.response.text}")
        except Exception as e:
            raise OpenAPIError(f"Failed to load OpenAPI spec: {e}")
            
        if not isinstance(spec, dict) or "paths" not in spec or "info" not in spec:
            raise OpenAPIError("Invalid OpenAPI spec: Missing required properties 'paths' or 'info'")
            
        return spec

    @staticmethod
    def extract_server_url(spec: Dict[str, Any], openapi_url: str) -> str:
        """Extract server URL from OpenAPI spec."""
        servers = spec.get("servers")
        parsed_url = urlparse(openapi_url)
        
        # Try to get server URL from servers field
        raw_url = ""
        if isinstance(servers, list) and servers:
            raw_url = servers[0].get("url", "")
        elif isinstance(servers, dict):
            raw_url = servers.get("url", "")
            
        # Fallback to deriving from openapi_url
        if not raw_url:
            base = parsed_url.path.rsplit('/', 1)[0]
            raw_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base}"
            
        # Normalize server URL
        if raw_url.startswith("/"):
            server_url = f"{parsed_url.scheme}://{parsed_url.netloc}{raw_url}"
        elif not raw_url.startswith(("http://", "https://")):
            server_url = f"https://{raw_url}"
        else:
            server_url = raw_url
            
        return server_url


class OpenAPIParser:
    """Parses OpenAPI specifications into operation metadata."""
    
    def __init__(self, sanitizer_func):
        self._sanitize_name = sanitizer_func

    def parse_operations(self, spec: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Parse operations from OpenAPI spec into tool metadata."""
        operations = {}
        
        for path, path_item in spec.get("paths", {}).items():
            for method, operation in path_item.items():
                if method.lower() not in {"get", "post", "put", "delete", "patch", "head", "options"}:
                    continue
                    
                # Process request body as parameter
                self._process_request_body(operation)
                
                # Extract response schema
                response_schema = self._extract_response_schema(operation)
                
                # Generate operation ID
                raw_op_id = operation.get("operationId") or f"{method}_{path.replace('/', '_').replace('{', '').replace('}', '')}"
                sanitized_op_id = self._sanitize_name(raw_op_id)
                
                # Get operation summary/description
                summary = operation.get("description") or operation.get("summary") or sanitized_op_id
                
                operations[sanitized_op_id] = {
                    "summary": summary,
                    "parameters": operation.get("parameters", []),
                    "path": path,
                    "method": method.upper(),
                    "responseSchema": response_schema,
                    "tags": operation.get("tags", [])
                }
                
        logging.info("Parsed %d operations from OpenAPI spec", len(operations))
        return operations

    def _process_request_body(self, operation: Dict[str, Any]) -> None:
        """Convert requestBody to parameter for easier handling."""
        if "requestBody" not in operation:
            return
            
        req_body = operation["requestBody"]
        body_schema = {}
        
        if "content" in req_body and "application/json" in req_body["content"]:
            body_schema = req_body["content"]["application/json"].get("schema", {})
            
        # Add body as a parameter
        operation.setdefault("parameters", []).append({
            "name": "body",
            "in": "body",
            "required": req_body.get("required", False),
            "schema": body_schema,
            "description": "Request body"
        })

    def _extract_response_schema(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Extract response schema from 200 response."""
        responses = operation.get("responses", {})
        if "200" not in responses:
            return None
            
        response_200 = responses["200"]
        content = response_200.get("content", {})
        
        if "application/json" in content:
            return content["application/json"].get("schema")
            
        return None

    def extract_api_info(self, spec: Dict[str, Any]) -> Tuple[str, str]:
        """Extract API title and category from spec."""
        info = spec.get("info", {})
        title = info.get("title", "API")
        category = title.split()[0] if title else "API"
        return title, category