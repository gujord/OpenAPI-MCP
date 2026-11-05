# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""
FastMCP-compliant OpenAPI proxy server.
Follows FastMCP patterns and best practices.
"""

__all__ = ["FastMCPOpenAPIServer", "OpenAPITool", "main", "retry_with_backoff"]

import asyncio
import json
import logging
import math
import os
import random
import sys
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

import httpx
from fastmcp import FastMCP
from fastmcp.tools import Tool, ToolResult
from jsonschema import Draft202012Validator, ValidationError
from pydantic import Field
from referencing import Registry
from referencing.exceptions import Unresolvable
from starlette.responses import JSONResponse

from openapi_mcp.request_support import validate_operation_support

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0  # seconds
DEFAULT_RETRY_MAX_DELAY = 30.0  # seconds
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
RETRYABLE_METHODS = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}


async def retry_with_backoff(
    func,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    max_delay: float = DEFAULT_RETRY_MAX_DELAY,
    retryable_exceptions: tuple = (httpx.ConnectError, httpx.TimeoutException),
    logger: Optional[logging.Logger] = None,
):
    """
    Execute an async function with exponential backoff retry logic.

    Args:
        func: Async function to execute (should be a coroutine function or awaitable)
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        retryable_exceptions: Tuple of exception types that should trigger a retry
        logger: Optional logger for retry messages

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                # Exponential backoff with jitter
                delay = min(base_delay * (2**attempt) + random.SystemRandom().uniform(0, 1), max_delay)
                if logger:
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                await asyncio.sleep(delay)
            else:
                if logger:
                    logger.error(f"Request failed after {max_retries + 1} attempts: {e}")
                raise
        except httpx.HTTPStatusError as e:
            # Retry on certain status codes (e.g., 429, 5xx)
            if e.response.status_code in RETRYABLE_STATUS_CODES:
                last_exception = e
                if attempt < max_retries:
                    # Check for Retry-After header
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                            if not math.isfinite(delay):
                                raise ValueError("Non-finite Retry-After")
                        except ValueError:
                            delay = base_delay * (2**attempt)
                    else:
                        delay = min(base_delay * (2**attempt) + random.SystemRandom().uniform(0, 1), max_delay)

                    delay = max(0.0, min(delay, max_delay))
                    if logger:
                        logger.warning(
                            f"Request failed with status {e.response.status_code} "
                            f"(attempt {attempt + 1}/{max_retries + 1}). Retrying in {delay:.2f}s..."
                        )
                    await asyncio.sleep(delay)
                else:
                    if logger:
                        logger.error(
                            f"Request failed with status {e.response.status_code} " f"after {max_retries + 1} attempts"
                        )
                    raise
            else:
                # Non-retryable status code
                raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


try:
    from .auth import AuthenticationManager
    from .config import ServerConfig
    from .exceptions import ConfigurationError, OpenAPIError
    from .openapi_loader import OpenAPILoader, OpenAPIParser
    from .request_handler import RequestHandler
    from .schema_converter import NameSanitizer, SchemaConverter
except ImportError:
    from auth import AuthenticationManager
    from config import ServerConfig
    from exceptions import ConfigurationError, OpenAPIError
    from openapi_loader import OpenAPILoader, OpenAPIParser
    from request_handler import RequestHandler
    from schema_converter import NameSanitizer, SchemaConverter


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


class OpenAPICallTool(Tool):
    """Expose an OpenAPI schema directly, including non-Python parameter names."""

    callback: Callable[..., Awaitable[Dict[str, Any]]] = Field(exclude=True)

    async def run(self, arguments: Dict[str, Any]) -> ToolResult:
        try:
            # The empty registry forbids fetching external schema references.
            Draft202012Validator(self.parameters, registry=Registry()).validate(arguments)
        except (ValidationError, Unresolvable):
            return ToolResult(content="Invalid tool arguments or unresolved schema reference", is_error=True)
        result = await self.callback(**arguments)
        return ToolResult(structured_content=result, is_error="error" in result)


class FastMCPOpenAPIServer:
    """FastMCP-based OpenAPI proxy server following best practices."""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.mcp = FastMCP(config.server_name)

        @self.mcp.custom_route("/health", methods=["GET"])
        async def health(request):
            """Report process liveness without calling the upstream API."""
            return JSONResponse({"status": "ok"})

        # Core components
        self.authenticator = AuthenticationManager(config)
        self.request_handler = RequestHandler(self.authenticator)

        # Server state
        self.openapi_spec: Dict[str, Any] = {}
        self.operations: List[OpenAPITool] = []
        self.server_url: str = ""
        self.api_info: Dict[str, Any] = {}
        self._initialization_started = False

        # Initialize logging with debug level based on config
        log_level = logging.DEBUG if config.debug else logging.INFO
        log_format = (
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s" if config.debug else "%(levelname)s - %(message)s"
        )
        logging.basicConfig(level=log_level, format=log_format)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        if config.debug:
            self.logger.debug("Debug mode enabled - verbose logging active")

    async def initialize(self):
        """Initialize the server with OpenAPI spec and register tools."""
        if self._initialization_started:
            raise RuntimeError("Create a new server instance to reload a specification or operation policy")
        self._initialization_started = True
        try:
            self.logger.debug(f"Loading OpenAPI spec from: {self.config.openapi_url}")

            # Get custom headers for loading the spec
            auth_headers = self.authenticator.get_custom_headers() if self.authenticator else None
            if auth_headers and self.config.debug:
                self.logger.debug(f"Using {len(auth_headers)} custom auth headers")

            # Load OpenAPI specification with auth headers
            self.openapi_spec = OpenAPILoader.load_spec(self.config.openapi_url, auth_headers)
            self.server_url = OpenAPILoader.extract_server_url(self.openapi_spec, self.config.openapi_url)
            self.logger.debug(f"Server URL: {self.server_url}")

            # Parse operations into tools
            parser = OpenAPIParser(NameSanitizer.sanitize_name)
            operations_info = parser.parse_operations(self.openapi_spec)
            self.logger.debug(f"Found {len(operations_info)} operations in spec")

            allowed = set(self.config.allowed_operations)
            available = {f"{info['method']} {info['path']}" for info in operations_info.values()}
            if allowed - available:
                raise ConfigurationError("Unknown allowed operations: " + ", ".join(sorted(allowed - available)))
            if self.config.operation_policy == "allowlist":
                operations_info = {
                    name: info
                    for name, info in operations_info.items()
                    if f"{info['method']} {info['path']}" in allowed
                }
                if not operations_info:
                    self.logger.warning(
                        "No API operations allowed; set MCP_ALLOWED_OPERATIONS to expose selected routes"
                    )
            else:
                self.logger.warning("All API operations are exposed by explicit MCP_OPERATION_POLICY=all")
            if {"server_info", "list_operations"} & operations_info.keys():
                raise OpenAPIError("An allowed API operation uses a reserved management-tool name")
            for info in operations_info.values():
                validate_operation_support(self.openapi_spec, info["path"], info["method"])

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
                    server_url=self.server_url,
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

        except (OpenAPIError, FileNotFoundError) as e:
            self.logger.error(f"Failed to initialize server: {e}")
            raise
        except (httpx.RequestError, ValueError, KeyError) as e:
            self.logger.error(f"Failed to initialize server: {e}")
            raise RuntimeError(f"Server initialization failed: {e}") from e

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

        # Register the tool with FastMCP using the decorator pattern
        tool_name = f"{self.config.server_name}_{tool.operation_id}"
        tool_description = f"[{self.config.server_name}] {tool.summary or tool.description}"

        schema = self._build_parameter_schema(tool)
        Draft202012Validator.check_schema(schema)
        self.mcp.add_tool(
            OpenAPICallTool(
                name=tool_name,
                description=tool_description,
                parameters=schema,
                callback=generic_tool_function,
            )
        )

    def _make_generic_tool_function(self, tool: OpenAPITool):
        """Create generic tool function for a specific tool."""

        async def generic_tool_function(
            dry_run: bool = False,
            req_id: Optional[str] = None,
            **kwargs: Any,
        ) -> Dict[str, Any]:
            """Generic tool function for OpenAPI operation."""
            try:
                kwargs["dry_run"] = dry_run

                if req_id is None:
                    req_id = f"{tool.operation_id}_{int(asyncio.get_event_loop().time())}"

                # Handle dry run
                if dry_run:
                    request_data, error = self.request_handler.prepare_request(
                        req_id, kwargs, tool.parameters, tool.path, tool.server_url, tool.operation_id
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
                                "body": req_body,
                            },
                        },
                    }

                # Execute real request
                request_data, error = self.request_handler.prepare_request(
                    req_id, kwargs, tool.parameters, tool.path, tool.server_url, tool.operation_id
                )

                if error:
                    return error

                full_url, req_params, req_headers, req_body, _ = request_data

                # Make HTTP request with retry logic
                retry_config = self.config.get_http_retry_config()

                # Log metadata, not URL/parameter/header/body values: APIs
                # can place secrets in any of those fields.
                self.logger.debug("Executing %s operation %s", tool.method.upper(), tool.operation_id)
                async with httpx.AsyncClient(timeout=retry_config["timeout"]) as client:

                    async def make_request():
                        response = await client.request(
                            method=tool.method, url=full_url, headers=req_headers, params=req_params, json=req_body
                        )
                        response.raise_for_status()
                        return response

                    response = await retry_with_backoff(
                        make_request,
                        max_retries=retry_config["max_retries"] if tool.method.upper() in RETRYABLE_METHODS else 0,
                        base_delay=retry_config["base_delay"],
                        max_delay=retry_config["max_delay"],
                        logger=self.logger,
                    )
                    # Handle response
                    try:
                        response_data = response.json()
                    except (ValueError, json.JSONDecodeError):
                        response_data = response.text

                    self.logger.debug("Response: %d (%d bytes)", response.status_code, len(response.content))

                    return {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {
                            "status_code": response.status_code,
                            "headers": dict(response.headers),
                            "data": response_data,
                        },
                    }

            except httpx.HTTPStatusError as e:
                self.logger.error(f"Tool {tool.operation_id} HTTP error: {e.response.status_code}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id or "unknown",
                    "error": {
                        "code": -32603,
                        "message": f"HTTP error {e.response.status_code}: {e.response.text[:200]}",
                    },
                }
            except httpx.RequestError as e:
                self.logger.error(f"Tool {tool.operation_id} request error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id or "unknown",
                    "error": {"code": -32603, "message": f"Request failed: {str(e)}"},
                }
            except (ValueError, KeyError, TypeError) as e:
                self.logger.error(f"Tool {tool.operation_id} error: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": req_id or "unknown",
                    "error": {"code": -32602, "message": f"Invalid parameter: {str(e)}"},
                }

        return generic_tool_function

    def _build_parameter_schema(self, tool: OpenAPITool) -> Dict[str, Any]:
        """Build parameter schema for tool from OpenAPI parameters."""
        schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}

        for param in tool.parameters:
            param_name = param.get("name", "")
            param_schema = param.get("schema", {})
            if param_name in {"dry_run", "req_id", "kwargs"}:
                raise OpenAPIError(f"Operation {tool.operation_id} uses reserved parameter {param_name}")
            if param_name in schema["properties"]:
                raise OpenAPIError(f"Operation {tool.operation_id} has ambiguous parameter {param_name}")

            schema["properties"][param_name] = {
                "description": param.get("description", ""),
                **param_schema,
            }

            if param.get("required", False):
                schema["required"].append(param_name)

        # Add common parameters
        schema["properties"]["dry_run"] = {
            "type": "boolean",
            "description": "Show request details without executing",
            "default": False,
        }
        schema["properties"]["req_id"] = {"type": "string", "description": "Optional correlation ID"}

        # Preserve local component references without allowing network retrieval.
        def convert(value):
            if isinstance(value, list):
                return [convert(item) for item in value]
            if not isinstance(value, dict):
                return value
            result = {key: convert(item) for key, item in value.items()}
            ref = result.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
                result["$ref"] = ref.replace("#/components/schemas/", "#/$defs/", 1)
            if result.pop("nullable", False) and "type" in result:
                kind = result["type"]
                result["type"] = kind + ["null"] if isinstance(kind, list) else [kind, "null"]
            return result

        schema["$defs"] = self.openapi_spec.get("components", {}).get("schemas", {})

        return cast(Dict[str, Any], convert(schema))

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
                "operation_policy": self.config.operation_policy,
                "authentication": {
                    "oauth_configured": self.config.is_oauth_configured(),
                    "username_auth_configured": self.config.is_username_auth_configured(),
                },
            }

        async def list_operations() -> Dict[str, Any]:
            """List all available API operations."""
            operations = []
            for tool in self.operations:
                operations.append(
                    {
                        "operation_id": tool.operation_id,
                        "method": tool.method,
                        "path": tool.path,
                        "summary": tool.summary,
                        "description": tool.description,
                        "tool_name": f"{self.config.server_name}_{tool.operation_id}",
                    }
                )

            return {"total_operations": len(operations), "operations": operations}

        # Register management tools using the decorator pattern
        self.mcp.tool(
            name=f"{self.config.server_name}_server_info",
            description=f"Get information about the {self.config.server_name} API server",
        )(server_info)

        self.mcp.tool(
            name=f"{self.config.server_name}_list_operations",
            description=f"List all available API operations for {self.config.server_name}",
        )(list_operations)

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
                    return json.dumps(SchemaConverter.convert_openapi_to_mcp_schema(schema_data))

                return get_schema

            # Use the resource decorator to register
            self.mcp.resource(
                uri=f"schema://{safe_name}",
                name=safe_name,
                description=f"[{self.config.server_name}] Schema for {schema_name}",
                mime_type="application/json",
            )(make_schema_resource(schema))

    def _register_prompts(self):
        """Register contextual prompts for API usage."""

        async def api_usage_prompt() -> str:
            """Generate API usage prompt."""
            api_title = self.api_info.get("title", "API")
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

            content += "\n## Usage Tips:\n"
            content += "- Use `dry_run=true` to see request details without executing\n"
            content += f"- Check the `{self.config.server_name}_server_info` tool for server details\n"
            content += f"- Use `{self.config.server_name}_list_operations` to see all available operations\n"

            return content

        # Use the prompt decorator to register with name and description
        self.mcp.prompt(
            name=f"{self.config.server_name}_api_usage",
            description=f"Guide for using the {self.api_info.get('title', 'API')} via {self.config.server_name}",
        )(api_usage_prompt)

    def run_stdio(self):
        """Run server with stdio transport (for MCP clients)."""
        self.mcp.run()

    async def run_sse_async(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with SSE transport asynchronously."""
        import uvicorn

        app = self.get_sse_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    async def run_http_async(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with streamable HTTP transport asynchronously."""
        import uvicorn

        app = self.get_http_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    def run_sse(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with SSE transport."""
        # FastMCP uses uvicorn to run SSE server
        import uvicorn

        app = self.get_sse_app()
        uvicorn.run(app, host=host, port=port)

    def run_http(self, host: str = "127.0.0.1", port: int = 8000):
        """Run server with streamable HTTP transport."""
        import uvicorn

        app = self.get_http_app()
        uvicorn.run(app, host=host, port=port)

    def get_sse_app(self):
        """Get SSE app for custom deployment."""
        return self._get_http_app("sse")

    def get_http_app(self):
        """Get HTTP app for custom deployment."""
        return self._get_http_app("http")

    def _get_http_app(self, transport):
        hosts = [host.strip() for host in self.config.mcp_allowed_hosts.split(",") if host.strip()]
        return self.mcp.http_app(
            transport=transport,
            host_origin_protection=True,
            allowed_hosts=hosts or None,
            allowed_origins=[origin.strip() for origin in self.config.mcp_cors_origins.split(",") if origin.strip()],
        )


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
            transport_type = os.environ.get("MCP_TRANSPORT_TYPE", "http").lower()

            if transport_type == "http" or transport_type == "streamable":
                logging.info(
                    f"Starting FastMCP Streamable HTTP server on {config.mcp_http_host}:{config.mcp_http_port}"
                )
                server.run_http(host=config.mcp_http_host, port=config.mcp_http_port)
            else:
                logging.info(f"Starting FastMCP SSE server on {config.mcp_http_host}:{config.mcp_http_port}")
                server.run_sse(host=config.mcp_http_host, port=config.mcp_http_port)
        else:
            logging.info("Starting FastMCP stdio server")
            server.run_stdio()

    except ConfigurationError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    except (OpenAPIError, FileNotFoundError) as e:
        logging.error(f"Failed to load OpenAPI spec: {e}")
        sys.exit(1)
    except RuntimeError as e:
        logging.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
