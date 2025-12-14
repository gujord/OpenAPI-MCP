# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""Type definitions for OpenAPI-MCP server.

This module contains TypedDict definitions for structured data used throughout
the codebase, providing better type safety and documentation.
"""

__all__ = [
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

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict, NotRequired


class ParameterDefinition(TypedDict, total=False):
    """OpenAPI parameter definition."""

    name: str
    in_: str  # 'in' is reserved keyword, use 'in_' but actual key is 'in'
    required: bool
    schema: Dict[str, Any]
    description: str


class OperationMetadata(TypedDict):
    """Metadata for an OpenAPI operation parsed into tool format."""

    summary: str
    parameters: List[Dict[str, Any]]
    path: str
    method: str
    responseSchema: Optional[Dict[str, Any]]
    tags: List[str]


class OAuthConfig(TypedDict):
    """OAuth authentication configuration."""

    client_id: Optional[str]
    client_secret: Optional[str]
    token_url: Optional[str]
    scope: str


class UsernameAuthConfig(TypedDict):
    """Username/password authentication configuration."""

    username: Optional[str]
    password: Optional[str]
    login_endpoint: Optional[str]


class SSEConfig(TypedDict):
    """SSE transport configuration."""

    enabled: bool
    host: str
    port: int


class MCPHTTPConfig(TypedDict):
    """MCP HTTP transport configuration."""

    enabled: bool
    host: str
    port: int
    cors_origins: List[str]
    message_size_limit: str
    batch_timeout: int
    session_timeout: int


class HTTPRetryConfig(TypedDict):
    """HTTP retry configuration."""

    max_retries: int
    base_delay: float
    max_delay: float
    timeout: float


class ToolMetadata(TypedDict):
    """Metadata for a registered MCP tool."""

    name: str
    description: str
    inputSchema: Dict[str, Any]


class RequestInfo(TypedDict, total=False):
    """Information about an HTTP request to be made."""

    url: str
    method: str
    params: Dict[str, Any]
    headers: Dict[str, str]
    body: Any
    dry_run: bool


class JSONRPCError(TypedDict):
    """JSON-RPC 2.0 error object."""

    code: int
    message: str
    data: NotRequired[Any]


class JSONRPCResponse(TypedDict, total=False):
    """JSON-RPC 2.0 response object."""

    jsonrpc: str
    id: Any
    result: Any
    error: JSONRPCError
