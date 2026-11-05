# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""OpenAPI MCP Server - A modular Model Context Protocol server for OpenAPI specifications."""

__version__ = "1.0.4"
__author__ = "Roger Gujord"
__license__ = "MIT"

from openapi_mcp.auth import AuthenticationManager
from openapi_mcp.config import ServerConfig
from openapi_mcp.exceptions import (
    AuthenticationError,
    ConfigurationError,
    MCPServerError,
    RequestExecutionError,
    ToolNotFoundError,
)
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer, main
from openapi_mcp.types import (
    HTTPRetryConfig,
    JSONRPCError,
    JSONRPCResponse,
    MCPHTTPConfig,
    OAuthConfig,
    OperationMetadata,
    ParameterDefinition,
    RequestInfo,
    SSEConfig,
    ToolMetadata,
    UsernameAuthConfig,
)

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "ServerConfig",
    "AuthenticationManager",
    "FastMCPOpenAPIServer",
    "main",
    "MCPServerError",
    "ConfigurationError",
    "AuthenticationError",
    "RequestExecutionError",
    "ToolNotFoundError",
    # Type definitions
    "OperationMetadata",
    "ParameterDefinition",
    "OAuthConfig",
    "UsernameAuthConfig",
    "SSEConfig",
    "MCPHTTPConfig",
    "HTTPRetryConfig",
    "ToolMetadata",
    "RequestInfo",
    "JSONRPCError",
    "JSONRPCResponse",
]
