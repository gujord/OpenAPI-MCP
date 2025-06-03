# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""
FastMCP-compliant OpenAPI proxy server.
Follows FastMCP patterns and best practices.
"""

import os
import sys
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
import httpx
from fastmcp import FastMCP

try:
    from .config import ServerConfig
    from .auth import AuthenticationManager
    from .openapi_loader import OpenAPILoader, OpenAPIParser
    from .request_handler import RequestHandler
    from .schema_converter import SchemaConverter, NameSanitizer
    from .exceptions import *
except ImportError:
    from config import ServerConfig
    from auth import AuthenticationManager
    from openapi_loader import OpenAPILoader, OpenAPIParser
    from request_handler import RequestHandler
    from schema_converter import SchemaConverter, NameSanitizer
    from exceptions import *


@dataclass
class OpenAPITool:
    """Represents an OpenAPI operation as an MCP tool."""
    operation_id: str
    method: str
    path: str
    summary: str
    description: str
    parameters: List[Dict[str, Any]]
    server_url: str


class FastMCPOpenAPIServer:
    """FastMCP-based OpenAPI proxy server following best practices."""
    
    def __init__(self, config: ServerConfig):
        self.config = config
        self.mcp = FastMCP(config.server_name)
        
        # Core components
        self.authenticator = AuthenticationManager(config)
        self.request_handler = RequestHandler(self.authenticator)
        
        # Server state
        self.openapi_spec: Dict[str, Any] = {}
        self.operations: List[OpenAPITool] = []
        self.server_url: str = ""
        self.api_info: Dict[str, Any] = {}
        
        # Initialize logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    async def initialize(self):
        """Initialize the server with OpenAPI spec and register tools."""
        try:
            # Load OpenAPI specification
            self.openapi_spec = OpenAPILoader.load_spec(self.config.openapi_url)
            self.server_url = OpenAPILoader.extract_server_url(
                self.openapi_spec, self.config.openapi_url
            )
            
            # Parse operations into tools
            parser = OpenAPIParser(NameSanitizer.sanitize_name)
            operations_info = parser.parse_operations(self.openapi_spec)
            
            # Extract API info
            self.api_info = self.openapi_spec.get("info", {})
            api_title = self.api_info.get("title", "API")
            
            # Create tool objects
            for op_id, info in operations_info.items():
                tool = OpenAPITool(
                    operation_id=op_id,
                    method=info["method"],
                    path=info["path"], 
                    summary=info.get("summary", ""),
                    description=info.get("description", ""),
                    parameters=info.get("parameters", []),
                    server_url=self.server_url
                )
                self.operations.append(tool)
            
            # Register all tools using FastMCP decorators
            self._register_tools()
            
            # Register resources
            self._register_resources()
            
            # Register prompts
            self._register_prompts()
            
            self.logger.info(f"Initialized OpenAPI proxy for {api_title}")
            self.logger.info(f"Registered {len(self.operations)} API operations as tools")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize server: {e}")
            raise
    
    def _register_tools(self):
        """Register OpenAPI operations as FastMCP tools using decorators."""
        
        # Register each OpenAPI operation as a tool
        for tool in self.operations:
            self._register_single_tool(tool)
        
        # Register server management tools
        self._register_management_tools()
    
    def _create_tool_function(self, tool: OpenAPITool):
        """Create a tool function for testing purposes."""
        return self._make_generic_tool_function(tool)
    
    def _register_single_tool(self, tool: OpenAPITool):
        """Register a single OpenAPI operation as an MCP tool."""
        
        # Create generic tool function
        generic_tool_function = self._make_generic_tool_function(tool)
        
        # Store function for testing
        tool._function = generic_tool_function
        
        # Register the tool with FastMCP
        self.mcp.add_tool(
            generic_tool_function,
            name=f"{self.config.server_name}_{tool.operation_id}",
            description=f"[{self.config.server_name}] {tool.summary or tool.description}"
        )
    
    def _make_generic_tool_function(self, tool: OpenAPITool):
        """Create generic tool function for a specific tool."""
        async def generic_tool_function(
            dry_run: bool = False,
            req_id: Optional[str] = None,
            # Common OpenAPI parameters
            id: Optional[str] = None,
            status: Optional[str] = None,
            tags: Optional[str] = None,
            name: Optional[str] = None,
            limit: Optional[int] = None,
            offset: Optional[int] = None,
            q: Optional[str] = None,
            query: Optional[str] = None,
            # Additional common parameters
            page: Optional[int] = None,
            size: Optional[int] = None,
            sort: Optional[str] = None,
            filter: Optional[str] = None,
            # Weather API specific
            lat: Optional[float] = None,
            lon: Optional[float] = None,
            altitude: Optional[int] = None
        ) -> Dict[str, Any]:
            """Generic tool function for OpenAPI operation."""
            try:
                # Build kwargs from function parameters
                import inspect
                frame = inspect.currentframe()
                args = inspect.getargvalues(frame)
                kwargs = {k: v for k, v in args.locals.items() 
                         if k != 'self' and v is not None and k not in ['frame', 'args']}
                
                if req_id is None:
                    req_id = f"{tool.operation_id}_{int(asyncio.get_event_loop().time())}"
                
                # Handle dry run
                if dry_run:
                    request_data, error = self.request_handler.prepare_request(
                        req_id,
                        kwargs,
                        tool.parameters,
                        tool.path,
                        tool.server_url,
                        tool.operation_id
                    )
                    if error:
                        return error
                    
                    full_url, req_params, req_headers, req_body, _ = request_data
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "dry_run": True,
                            "request": {
                                "method": tool.method,
                                "url": full_url,
                                "params": req_params,
                                "headers": req_headers,
                                "body": req_body
                            }
                        }
                    }
                
                # Execute real request
                request_data, error = self.request_handler.prepare_request(
                    req_id,
                    kwargs,
                    tool.parameters,
                    tool.path,
                    tool.server_url,
                    tool.operation_id
                )
                
                if error:
                    return error
                
                full_url, req_params, req_headers, req_body, _ = request_data
                
                # Make HTTP request
                async with httpx.AsyncClient() as client:
                    response = await client.request(
                        method=tool.method,
                        url=full_url,
                        headers=req_headers,
                        params=req_params,
                        json=req_body
                    )
                    
                    response.raise_for_status()
                    
                    # Handle response
                    try:
                        response_data = response.json()
                    except:
                        response_data = response.text
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                            "data": response_data
                        }
                    }
                    
            except Exception as e:
                self.logger.error(f"Tool {tool.operation_id} error: {e}")
                return {
                    "jsonrpc": "2.0", 
                    "id": req_id or "unknown",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
        
        return generic_tool_function
    
    def _build_parameter_schema(self, tool: OpenAPITool) -> Dict[str, Any]:
        """Build parameter schema for tool from OpenAPI parameters."""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param in tool.parameters:
            param_name = param.get("name", "")
            param_schema = param.get("schema", {})
            
            schema["properties"][param_name] = {
                "type": param_schema.get("type", "string"),
                "description": param.get("description", ""),
                **param_schema
            }
            
            if param.get("required", False):
                schema["required"].append(param_name)
        
        # Add common parameters
        schema["properties"]["dry_run"] = {
            "type": "boolean",
            "description": "Show request details without executing",
            "default": False
        }
        
        return schema
    
    def _register_management_tools(self):
        """Register server management tools."""
        
        async def server_info() -> Dict[str, Any]:
            """Get server information."""
            return {
                "server_name": self.config.server_name,
                "api_title": self.api_info.get("title", "API"),
                "api_version": self.api_info.get("version", "Unknown"),
                "api_description": self.api_info.get("description", ""),
                "server_url": self.server_url,
                "total_operations": len(self.operations),
                "authentication": {
                    "oauth_configured": self.config.is_oauth_configured(),
                    "username_auth_configured": self.config.is_username_auth_configured()
                }
            }
        
        async def list_operations() -> Dict[str, Any]:
            """List all available API operations."""
            operations = []
            for tool in self.operations:
                operations.append({
                    "operation_id": tool.operation_id,
                    "method": tool.method,
                    "path": tool.path,
                    "summary": tool.summary,
                    "description": tool.description,
                    "tool_name": f"{self.config.server_name}_{tool.operation_id}"
                })
            
            return {
                "total_operations": len(operations),
                "operations": operations
            }
        
        # Register management tools
        self.mcp.add_tool(
            server_info,
            name=f"{self.config.server_name}_server_info",
            description=f"Get information about the {self.config.server_name} API server"
        )
        
        self.mcp.add_tool(
            list_operations,
            name=f"{self.config.server_name}_list_operations", 
            description=f"List all available API operations for {self.config.server_name}"
        )
    
    def _register_resources(self):
        """Register OpenAPI schemas as MCP resources."""
        
        schemas = self.openapi_spec.get("components", {}).get("schemas", {})
        
        for schema_name, schema in schemas.items():
            resource_name = f"{self.config.server_name}_{schema_name}"
            safe_name = NameSanitizer.sanitize_resource_name(resource_name)
            
            # Create resource function with closure to capture schema
            def make_schema_resource(schema_data):
                async def get_schema() -> str:
                    """Get OpenAPI schema."""
                    return SchemaConverter.convert_openapi_to_mcp_schema(schema_data)
                return get_schema
            
            self.mcp.add_resource_fn(
                make_schema_resource(schema),
                uri=f"schema://{safe_name}",
                name=safe_name,
                description=f"[{self.config.server_name}] Schema for {schema_name}",
                mime_type="application/json"
            )
    
    def _register_prompts(self):
        """Register contextual prompts for API usage."""
        
        async def api_usage_prompt() -> str:
            """Generate API usage prompt."""
            api_title = self.api_info.get('title', 'API')
            content = f"""# {self.config.server_name} - {api_title} Usage Guide

This server provides access to {len(self.operations)} API operations from {api_title}.

## Available Operations:
"""
            
            for tool in self.operations[:10]:  # Show first 10 operations
                content += f"\n### {tool.operation_id}\n"
                content += f"- **Method:** {tool.method.upper()}\n"
                content += f"- **Path:** {tool.path}\n"
                content += f"- **Description:** {tool.summary or tool.description}\n"
                content += f"- **Tool Name:** `{self.config.server_name}_{tool.operation_id}`\n"
            
            if len(self.operations) > 10:
                content += f"\n... and {len(self.operations) - 10} more operations.\n"
            
            content += f"\n## Usage Tips:\n"
            content += f"- Use `dry_run=true` to see request details without executing\n"
            content += f"- Check the `{self.config.server_name}_server_info` tool for server details\n"
            content += f"- Use `{self.config.server_name}_list_operations` to see all available operations\n"
            
            return content
        
        self.mcp.add_prompt(
            api_usage_prompt,
            name=f"{self.config.server_name}_api_usage",
            description=f"Guide for using the {self.api_info.get('title', 'API')} via {self.config.server_name}"
        )
    
    def run_stdio(self):
        """Run server with stdio transport (for MCP clients)."""
        self.mcp.run()
    
    async def run_sse_async(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with SSE transport asynchronously."""
        import uvicorn
        app = self.mcp.sse_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    
    async def run_http_async(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with streamable HTTP transport asynchronously."""
        import uvicorn
        app = self.mcp.streamable_http_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()
    
    def run_sse(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with SSE transport."""
        # FastMCP uses uvicorn to run SSE server
        import uvicorn
        app = self.mcp.sse_app()
        uvicorn.run(app, host=host, port=port)
    
    def run_http(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with streamable HTTP transport."""
        import uvicorn
        app = self.mcp.streamable_http_app()
        uvicorn.run(app, host=host, port=port)
    
    def get_sse_app(self):
        """Get SSE app for custom deployment."""
        return self.mcp.sse_app()
    
    def get_http_app(self):
        """Get HTTP app for custom deployment.""" 
        return self.mcp.streamable_http_app()


def main():
    """Main entry point following FastMCP patterns."""
    try:
        # Load configuration
        config = ServerConfig()
        
        # Create and initialize server  
        server = FastMCPOpenAPIServer(config)
        
        # Initialize synchronously since FastMCP handles async internally
        import asyncio
        asyncio.run(server.initialize())
        
        # Choose transport based on configuration
        if config.mcp_http_enabled:
            # Check if we should use streamable HTTP or SSE
            transport_type = os.environ.get("MCP_TRANSPORT_TYPE", "sse").lower()
            
            if transport_type == "http" or transport_type == "streamable":
                logging.info(f"Starting FastMCP Streamable HTTP server on {config.mcp_http_host}:{config.mcp_http_port}")
                server.run_http(host=config.mcp_http_host, port=config.mcp_http_port)
            else:
                logging.info(f"Starting FastMCP SSE server on {config.mcp_http_host}:{config.mcp_http_port}")
                server.run_sse(host=config.mcp_http_host, port=config.mcp_http_port)
        else:
            logging.info("Starting FastMCP stdio server")
            server.run_stdio()
            
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()