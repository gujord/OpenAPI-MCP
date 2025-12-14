# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""
DEPRECATED: This module is deprecated and will be removed in a future version.

Please use `fastmcp_server.py` instead:

    from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer
    from openapi_mcp.config import ServerConfig

    config = ServerConfig()
    server = FastMCPOpenAPIServer(config)
    await server.initialize()
    server.run_stdio()

The FastMCPOpenAPIServer provides:
- Simpler API with better FastMCP integration
- Automatic retry logic with exponential backoff
- Debug logging support via MCP_DEBUG environment variable
- Better error handling and validation
"""

__all__ = [
    "MCPResource",
    "Prompt",
    "ResourceManager",
    "PromptGenerator",
    "MCPServer",
    "main",
]

import os
import sys
import time
import logging
import warnings
from typing import Dict, Any, List, Optional
from fastmcp import FastMCP

# Emit deprecation warning when module is imported
warnings.warn(
    "openapi_mcp.server is deprecated. Use openapi_mcp.fastmcp_server instead. "
    "See migration guide at https://github.com/gujord/OpenAPI-MCP#migration",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from .config import ServerConfig
    from .auth import AuthenticationManager
    from .openapi_loader import OpenAPILoader, OpenAPIParser
    from .request_handler import RequestHandler
    from .tool_factory import ToolMetadataBuilder, ToolFunctionFactory
    from .schema_converter import SchemaConverter, NameSanitizer, ResourceNameProcessor
    from .sse_handler import SSEManager, SSEToolFactory, ChunkProcessors
    from .sse_server import SSEServerManager
    from .mcp_transport import MCPHttpTransport
    from .exceptions import *
except ImportError:
    from config import ServerConfig
    from auth import AuthenticationManager
    from openapi_loader import OpenAPILoader, OpenAPIParser
    from request_handler import RequestHandler
    from tool_factory import ToolMetadataBuilder, ToolFunctionFactory
    from schema_converter import SchemaConverter, NameSanitizer, ResourceNameProcessor
    from sse_handler import SSEManager, SSEToolFactory, ChunkProcessors
    from sse_server import SSEServerManager
    from mcp_transport import MCPHttpTransport
    from exceptions import *


class MCPResource:
    """Represents an MCP resource."""

    def __init__(self, name: str, schema: dict, description: str):
        self.name = name
        self.schema = schema
        self.description = description
        self.uri = f"/resource/{name}"


class Prompt:
    """Represents an MCP prompt."""

    def __init__(self, name: str, content: str, description: str = ""):
        self.name = name
        self.content = content
        self.description = description


class ResourceManager:
    """Manages MCP resources from OpenAPI schemas."""

    def __init__(self, server_name: str, api_category: Optional[str] = None):
        self.server_name = server_name
        self.api_category = api_category
        self.registered_resources: Dict[str, Dict[str, Any]] = {}

    def register_resources_from_openapi(self, openapi_spec: Dict[str, Any], mcp_server: FastMCP) -> int:
        """Register resources from OpenAPI component schemas."""
        schemas = openapi_spec.get("components", {}).get("schemas", {})
        resource_count = 0

        for schema_name, schema in schemas.items():
            prefixed_name = f"{self.server_name}_{schema_name}"
            safe_name = NameSanitizer.sanitize_resource_name(prefixed_name)

            resource_schema = SchemaConverter.convert_openapi_to_mcp_schema(schema)
            resource_description = f"[{self.server_name}] {schema.get('description', f'Resource for {schema_name}')}"

            resource_obj = MCPResource(name=safe_name, schema=resource_schema, description=resource_description)

            mcp_server.add_resource(resource_obj)
            self.registered_resources[safe_name] = {
                "schema": resource_schema,
                "metadata": {
                    "name": safe_name,
                    "description": resource_description,
                    "serverInfo": {"name": self.server_name},
                    "tags": ["resource", self.server_name] + ([self.api_category] if self.api_category else []),
                },
            }
            resource_count += 1

        return resource_count


class PromptGenerator:
    """Generates MCP prompts from OpenAPI specifications."""

    def __init__(self, server_name: str, openapi_spec: Dict[str, Any]):
        self.server_name = server_name
        self.openapi_spec = openapi_spec

    def generate_api_usage_prompt(self) -> Prompt:
        """Generate general API usage prompt."""
        info = self.openapi_spec.get("info", {})
        api_title = info.get("title", "API")

        content = f"""# {self.server_name} - API Usage Guide for {api_title}

This API provides the following capabilities:
"""

        for path, methods in self.openapi_spec.get("paths", {}).items():
            for method, details in methods.items():
                if method.lower() in {"get", "post", "put", "delete", "patch"}:
                    raw_tool_name = details.get("operationId") or f"{method}_{path}"
                    tool_name = f"{self.server_name}_{raw_tool_name}"
                    content += f"\n## {tool_name}\n"
                    content += f"- Path: `{path}` (HTTP {method.upper()})\n"
                    content += (
                        f"- Description: {details.get('description') or details.get('summary', 'No description')}\n"
                    )

                    if details.get("parameters"):
                        content += "- Parameters:\n"
                        for param in details.get("parameters", []):
                            required = "Required" if param.get("required") else "Optional"
                            content += f"  - `{param.get('name')}` ({param.get('in')}): {param.get('description', 'No description')} [{required}]\n"

        prompt_name = f"{self.server_name}_api_general_usage"
        prompt_description = f"[{self.server_name}] General guidance for using {api_title} API"

        return Prompt(prompt_name, content, prompt_description)

    def generate_example_prompts(self) -> List[Prompt]:
        """Generate example usage prompts for CRUD operations."""
        crud_ops = self._identify_crud_operations()
        prompts = []

        for resource, operations in crud_ops.items():
            content = f"""# {self.server_name} - Examples for working with {resource}

Common scenarios for handling {resource} resources:
"""

            if "list" in operations:
                prefixed_op = f"{self.server_name}_{operations['list']}"
                content += f"""
## Listing {resource} resources

To list all {resource} resources:
```
{{{{tool.{prefixed_op}()}}}}
```
"""

            if "get" in operations:
                prefixed_op = f"{self.server_name}_{operations['get']}"
                content += f"""
## Getting a specific {resource}

To retrieve a specific {resource} by ID:
```
{{{{tool.{prefixed_op}(id="example-id")}}}}
```
"""

            if "create" in operations:
                prefixed_op = f"{self.server_name}_{operations['create']}"
                content += f"""
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
            prompts.append(Prompt(prompt_name, content, prompt_description))

        return prompts

    def _identify_crud_operations(self) -> Dict[str, Dict[str, str]]:
        """Identify CRUD operations from OpenAPI paths."""
        crud_ops = {}

        for path, methods in self.openapi_spec.get("paths", {}).items():
            path_parts = [p for p in path.split("/") if p and not p.startswith("{")]
            if not path_parts:
                continue

            resource = ResourceNameProcessor.singularize_resource(path_parts[-1])
            if resource not in crud_ops:
                crud_ops[resource] = {}

            for method, details in methods.items():
                op_id = NameSanitizer.sanitize_name(details.get("operationId") or f"{method}_{path}")

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


class MCPServer:
    """Main MCP server class with modular architecture.

    .. deprecated::
        Use :class:`openapi_mcp.fastmcp_server.FastMCPOpenAPIServer` instead.
    """

    def __init__(self, config: ServerConfig):
        warnings.warn(
            "MCPServer is deprecated. Use FastMCPOpenAPIServer from " "openapi_mcp.fastmcp_server instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.config = config
        self.server_name = config.server_name
        self.mcp = FastMCP(self.server_name)

        # Initialize components
        self.authenticator = AuthenticationManager(config)
        self.request_handler = RequestHandler(self.authenticator)
        self.resource_manager = None

        # SSE components (deprecated - kept for backward compatibility)
        self.sse_manager = SSEManager() if config.sse_enabled else None
        self.sse_server_manager = None
        self.sse_tool_factory = None

        if self.sse_manager:
            self.sse_server_manager = SSEServerManager(self.sse_manager, config.sse_host, config.sse_port)
            self.sse_tool_factory = SSEToolFactory(self.sse_manager)
            logging.info("SSE support enabled (deprecated - use MCP_HTTP_ENABLED)")

        # MCP HTTP Transport
        self.mcp_transport = None
        if config.mcp_http_enabled:
            self.mcp_transport = MCPHttpTransport(
                mcp_server=self,
                host=config.mcp_http_host,
                port=config.mcp_http_port,
                cors_origins=config.mcp_cors_origins,
                message_size_limit=config.mcp_message_size_limit,
                batch_timeout=config.mcp_batch_timeout,
                session_timeout=config.mcp_session_timeout,
            )
            logging.info(f"MCP HTTP transport enabled on {config.mcp_http_host}:{config.mcp_http_port}")

        # Server state
        self.registered_tools: Dict[str, Dict[str, Any]] = {}
        self.openapi_spec: Dict[str, Any] = {}
        self.operations_info: Dict[str, Dict[str, Any]] = {}
        self.api_category: Optional[str] = None

    def initialize(self):
        """Initialize the server with OpenAPI spec and components."""
        try:
            # Get custom headers for loading the spec
            auth_headers = self.authenticator.get_custom_headers() if self.authenticator else None

            # Load OpenAPI spec with auth headers
            self.openapi_spec = OpenAPILoader.load_spec(self.config.openapi_url, auth_headers)
            server_url = OpenAPILoader.extract_server_url(self.openapi_spec, self.config.openapi_url)

            # Parse operations
            parser = OpenAPIParser(NameSanitizer.sanitize_name)
            self.operations_info = parser.parse_operations(self.openapi_spec)

            # Extract API info
            api_title, self.api_category = parser.extract_api_info(self.openapi_spec)

            # Initialize resource manager
            self.resource_manager = ResourceManager(self.server_name, self.api_category)

            # Initialize tool factory
            self.tool_factory = ToolFunctionFactory(self.request_handler, server_url)
            self.metadata_builder = ToolMetadataBuilder(self.server_name, self.api_category)

            logging.info(
                "Loaded API: %s (version: %s)", api_title, self.openapi_spec.get("info", {}).get("version", "Unknown")
            )

        except Exception as e:
            logging.error("Failed to initialize server: %s", e)
            raise

    def register_openapi_tools(self) -> int:
        """Register tools from OpenAPI operations."""
        tool_count = 0

        for op_id, info in self.operations_info.items():
            try:
                # Create tool function
                tool_function = self.tool_factory.create_tool_function(
                    op_id, info["method"], info["path"], info.get("parameters", [])
                )

                # Build metadata
                tool_metadata = self.metadata_builder.build_tool_metadata({op_id: info})[0]

                # Note: Custom streaming support removed for MCP compliance
                # MCP transport layer handles streaming via SSE according to official spec

                # Register tool
                self._add_tool(op_id, tool_function, info.get("summary", op_id), tool_metadata)
                tool_count += 1

            except Exception as e:
                logging.error("Failed to register tool for operation %s: %s", op_id, e)

        return tool_count

    def register_standard_tools(self):
        """Register standard MCP tools."""
        self._add_tool("initialize", self._initialize_tool, "Initialize MCP server.")
        self._add_tool("tools_list", self._tools_list_tool, "List available tools with extended metadata.")
        self._add_tool("tools_call", self._tools_call_tool, "Call a tool by name with provided arguments.")

        # Register SSE-specific tools if enabled
        if self.sse_manager:
            self._add_tool("sse_connections", self._sse_connections_tool, "Get SSE connection information.")
            self._add_tool("sse_broadcast", self._sse_broadcast_tool, "Broadcast message to all SSE connections.")

    def register_resources(self) -> int:
        """Register resources from OpenAPI schemas."""
        if not self.resource_manager:
            return 0
        return self.resource_manager.register_resources_from_openapi(self.openapi_spec, self.mcp)

    def generate_prompts(self) -> int:
        """Generate and register prompts."""
        prompt_generator = PromptGenerator(self.server_name, self.openapi_spec)

        # Generate general usage prompt
        general_prompt = prompt_generator.generate_api_usage_prompt()
        self.mcp.add_prompt(general_prompt)

        # Generate example prompts
        example_prompts = prompt_generator.generate_example_prompts()
        for prompt in example_prompts:
            self.mcp.add_prompt(prompt)

        return 1 + len(example_prompts)

    def _add_tool(self, name: str, func: Any, description: str, metadata: Optional[Dict[str, Any]] = None):
        """Add a tool to the server."""
        prefixed_name = f"{self.server_name}_{name}"
        safe_name = NameSanitizer.sanitize_tool_name(prefixed_name)
        enhanced_description = f"[{self.server_name}] {description}"

        if metadata is None:
            metadata = {
                "name": safe_name,
                "description": enhanced_description,
                "tags": ["openapi", "api", self.server_name],
                "serverInfo": {"name": self.server_name},
            }
        else:
            metadata["name"] = safe_name
            metadata["description"] = enhanced_description
            metadata.setdefault("tags", ["openapi", "api", self.server_name])
            metadata["serverInfo"] = {"name": self.server_name}

        self.registered_tools[safe_name] = {"function": func, "metadata": metadata}
        # Use the tool decorator pattern for FastMCP compatibility
        self.mcp.tool(name=safe_name, description=enhanced_description)(func)

    def _initialize_tool(self, req_id: Any = None, **kwargs):
        """Initialize tool implementation."""
        server_description = self.openapi_spec.get("info", {}).get(
            "description", f"OpenAPI Proxy for {self.server_name}"
        )
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
                    "tags": ["openapi", "api", self.server_name] + ([self.api_category] if self.api_category else []),
                },
            },
        }

    def _tools_list_tool(self, req_id: Any = None):
        """List tools implementation."""
        tool_list = [data["metadata"] for data in self.registered_tools.values()]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tool_list}}

    def _tools_call_tool(self, req_id: Any = None, name: str = None, arguments: Optional[Dict[str, Any]] = None):
        """Call tool implementation."""
        if not name:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Missing tool name"}}

        # Handle case where user forgot the server prefix
        if name not in self.registered_tools:
            prefixed_name = f"{self.server_name}_{name}"
            if prefixed_name in self.registered_tools:
                name = prefixed_name
            else:
                error = ToolNotFoundError(name, f"{self.server_name}_{name}")
                return error.to_json_rpc_error(req_id)

        try:
            func = self.registered_tools[name]["function"]
            return func(req_id=req_id, **(arguments or {}))
        except Exception as e:
            logging.error("Error calling tool %s: %s", name, e)
            error = RequestExecutionError(str(e))
            return error.to_json_rpc_error(req_id)

    def _get_chunk_processor(self, operation_info: Dict[str, Any]):
        """Determine appropriate chunk processor for an operation."""
        response_schema = operation_info.get("responseSchema", {})

        # Check for common streaming content types
        if "application/json" in str(response_schema):
            return ChunkProcessors.json_lines_processor
        elif "text/csv" in str(response_schema):
            return ChunkProcessors.csv_processor
        else:
            return ChunkProcessors.text_processor

    def _sse_connections_tool(self, req_id: Any = None, **kwargs):
        """SSE connections information tool."""
        if not self.sse_manager:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "SSE not enabled"}}

        connections_info = []
        for connection_id, connection in self.sse_manager.connections.items():
            connections_info.append(
                {
                    "connection_id": connection_id,
                    "connected": connection.connected,
                    "last_heartbeat": connection.last_heartbeat,
                    "heartbeat_interval": connection.heartbeat_interval,
                }
            )

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "active_connections": len(connections_info),
                "connections": connections_info,
                "sse_server_url": self.sse_server_manager.get_health_url() if self.sse_server_manager else None,
            },
        }

    def _sse_broadcast_tool(self, req_id: Any = None, message: str = None, **kwargs):
        """SSE broadcast tool."""
        if not self.sse_manager:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "SSE not enabled"}}

        if not message:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "Missing 'message' parameter"}}

        import asyncio

        try:
            from .sse_handler import SSEEvent, SSEEventType
        except ImportError:
            from sse_handler import SSEEvent, SSEEventType

        async def broadcast():
            event = SSEEvent(type=SSEEventType.DATA, data={"broadcast_message": message, "from": "mcp_server"})
            await self.sse_manager.broadcast_to_all(event)

        try:
            # Run the broadcast
            asyncio.create_task(broadcast())

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "success": True,
                    "message": "Broadcast initiated",
                    "connection_count": self.sse_manager.get_connection_count(),
                },
            }
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Broadcast failed: {e}"}}

    async def start_sse_server(self):
        """Start the SSE HTTP server if enabled."""
        if self.sse_server_manager:
            await self.sse_server_manager.start()

    async def stop_sse_server(self):
        """Stop the SSE HTTP server if running."""
        if self.sse_server_manager:
            await self.sse_server_manager.stop()

    def run(self):
        """Run the MCP server."""
        import asyncio

        # Choose transport mode
        if self.mcp_transport:
            # Run with MCP HTTP transport
            async def run_with_mcp_transport():
                try:
                    await self.mcp_transport.start()
                except KeyboardInterrupt:
                    logging.info("Shutting down MCP HTTP transport...")
                    await self.mcp_transport.stop()

            asyncio.run(run_with_mcp_transport())

        elif self.sse_server_manager:
            # Backward compatibility: Run with deprecated SSE server
            async def run_with_sse():
                await self.start_sse_server()
                # Give SSE server time to start
                await asyncio.sleep(1)
                # Run MCP server (this is blocking)
                self.mcp.run(transport="stdio")

            try:
                asyncio.run(run_with_sse())
            except KeyboardInterrupt:
                logging.info("Shutting down servers...")
                asyncio.run(self.stop_sse_server())
        else:
            # Default: stdio transport
            self.mcp.run(transport="stdio")


def main():
    """Main entry point.

    .. deprecated::
        Use ``openapi_mcp.fastmcp_server.main()`` instead.
    """
    warnings.warn(
        "openapi_mcp.server.main() is deprecated. " "Use openapi_mcp.fastmcp_server.main() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        # Load configuration
        config = ServerConfig()

        logging.info("Starting OpenAPI-MCP server with name: %s", config.server_name)
        logging.info("OpenAPI URL: %s", config.openapi_url)

        start_time = time.time()

        # Create and initialize server
        server = MCPServer(config)
        server.initialize()

        # Register components
        api_tool_count = server.register_openapi_tools()
        server.register_standard_tools()
        resource_count = server.register_resources()
        prompt_count = server.generate_prompts()

        # Log summary
        total_tools = len(server.registered_tools)
        setup_time = time.time() - start_time

        logging.info("Successfully registered %d/%d API tools", api_tool_count, len(server.operations_info))
        logging.info("Total registered tools: %d (API tools: %d, Standard tools: 3)", total_tools, api_tool_count)
        logging.info("Total registered resources: %d", resource_count)
        logging.info("Generated %d prompts", prompt_count)
        logging.info("Server setup completed in %.2f seconds", setup_time)
        logging.info("Server %s ready", config.server_name)

        # Start server
        logging.info("Starting MCP server...")
        server.run()

    except ConfigurationError as e:
        logging.error("Configuration error: %s", e.message)
        sys.exit(1)
    except Exception as e:
        logging.error("Failed to start server: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    main()
