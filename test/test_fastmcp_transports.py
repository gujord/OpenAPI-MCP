# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""Regression tests for supported FastMCP transport APIs."""

import inspect
from typing import Any, Dict, List, Tuple
from unittest.mock import Mock

import pytest
from fastmcp import FastMCP

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer, OpenAPITool
from openapi_mcp.request_handler import RequestHandler


class TransportRecorder:
    """Record transport calls without opening network listeners."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, Dict[str, Any]]] = []

    def run(self, transport: str, **kwargs: Any) -> None:
        """Record a synchronous transport invocation."""
        self.calls.append((transport, kwargs))

    async def run_async(self, transport: str, **kwargs: Any) -> None:
        """Record an asynchronous transport invocation."""
        self.calls.append((transport, kwargs))


def make_server() -> FastMCPOpenAPIServer:
    """Create a server without loading an OpenAPI document."""
    config = ServerConfig(OPENAPI_URL="test/fixtures/weather.yaml")
    return FastMCPOpenAPIServer(config)


@pytest.mark.parametrize(
    "app_method,expected_paths",
    [
        ("get_http_app", {"/mcp"}),
        ("get_sse_app", {"/sse", "/messages"}),
    ],
)
def test_transport_apps_use_supported_fastmcp_api(app_method: str, expected_paths: set[str]) -> None:
    """Build both network transports through FastMCP's public app API."""
    server = make_server()

    app = getattr(server, app_method)()
    route_paths = {route.path for route in app.routes}

    assert expected_paths.issubset(route_paths)


@pytest.mark.parametrize(
    "run_method,expected_transport",
    [
        ("run_stdio", "stdio"),
        ("run_http", "http"),
        ("run_sse", "sse"),
    ],
)
def test_sync_transport_runners_delegate_to_fastmcp(run_method: str, expected_transport: str) -> None:
    """Delegate synchronous transport startup to FastMCP."""
    server = make_server()
    recorder = TransportRecorder()
    server.__dict__["mcp"] = recorder

    if expected_transport == "stdio":
        getattr(server, run_method)()
        expected_options: Dict[str, Any] = {}
    else:
        getattr(server, run_method)(host="0.0.0.0", port=8123)
        expected_options = {"host": "0.0.0.0", "port": 8123}

    assert recorder.calls == [(expected_transport, expected_options)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "run_method,expected_transport",
    [
        ("run_stdio_async", "stdio"),
        ("run_http_async", "http"),
        ("run_sse_async", "sse"),
    ],
)
async def test_async_transport_runners_delegate_to_fastmcp(run_method: str, expected_transport: str) -> None:
    """Delegate asynchronous transport startup to FastMCP."""
    server = make_server()
    recorder = TransportRecorder()
    server.__dict__["mcp"] = recorder

    if expected_transport == "stdio":
        await getattr(server, run_method)()
        expected_options: Dict[str, Any] = {}
    else:
        await getattr(server, run_method)(host="0.0.0.0", port=8123)
        expected_options = {"host": "0.0.0.0", "port": 8123}

    assert recorder.calls == [(expected_transport, expected_options)]


@pytest.mark.asyncio
async def test_tool_signature_supports_arbitrary_openapi_parameters() -> None:
    """OpenAPI names are exposed safely and restored before request handling."""
    server = object.__new__(FastMCPOpenAPIServer)
    authenticator = Mock()
    authenticator.add_auth_headers.side_effect = lambda headers: headers
    server.request_handler = RequestHandler(authenticator)
    tool = OpenAPITool(
        operation_id="getPetById",
        method="GET",
        path="/pet/{petId}",
        summary="Get a pet",
        description="",
        parameters=[
            {"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}},
            {"name": "x-user-id", "in": "header", "schema": {"type": "string"}},
            {"name": "class", "in": "query", "schema": {"type": "boolean"}},
            {"name": "dry_run", "in": "query", "schema": {"type": "string"}},
            {"name": "kwargs", "in": "query", "schema": {"type": "string"}},
            {"name": "x_user_id", "in": "query", "schema": {"type": "string"}},
        ],
        server_url="https://example.test",
    )

    tool_function = server._create_tool_function(tool)
    signature = inspect.signature(tool_function)

    assert list(signature.parameters) == [
        "petId",
        "x_user_id",
        "api_class",
        "api_dry_run",
        "api_kwargs",
        "x_user_id_2",
        "dry_run",
        "req_id",
    ]
    assert signature.parameters["petId"].annotation is int
    assert signature.parameters["petId"].default is inspect.Parameter.empty

    result = await tool_function(
        petId=7,
        x_user_id="header-value",
        api_class=True,
        api_dry_run="api-value",
        api_kwargs="api-kwargs",
        x_user_id_2="query-value",
        dry_run=True,
        req_id="request-7",
    )

    assert result["result"]["request"]["url"] == "https://example.test/pet/7"
    assert result["result"]["request"]["params"] == {
        "class": True,
        "dry_run": "api-value",
        "kwargs": "api-kwargs",
        "x_user_id": "query-value",
    }
    assert result["result"]["request"]["headers"] == {
        "x-user-id": "header-value",
        "User-Agent": "OpenAPI-MCP/1.0",
    }


@pytest.mark.asyncio
async def test_fastmcp_registers_dynamic_tool_schema() -> None:
    """FastMCP validates and publishes the generated function annotations."""
    server = object.__new__(FastMCPOpenAPIServer)
    server.request_handler = Mock()
    server.request_handler.prepare_request.return_value = (
        ("https://example.test/pet/9", {}, {}, None, True),
        None,
    )
    tool = OpenAPITool(
        operation_id="getPetById",
        method="GET",
        path="/pet/{petId}",
        summary="Get a pet",
        description="",
        parameters=[{"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}}],
        server_url="https://example.test",
    )
    tool_function = server._create_tool_function(tool)
    mcp = FastMCP("test")
    mcp.tool(name="test_getPetById")(tool_function)

    registered_tool = await mcp.get_tool("test_getPetById")

    assert registered_tool is not None
    assert registered_tool.parameters["required"] == ["petId"]
    assert registered_tool.parameters["properties"]["petId"] == {"type": "integer"}
    await registered_tool.run({"petId": 9, "dry_run": True, "req_id": "request-9"})
    request_kwargs = server.request_handler.prepare_request.call_args.args[1]
    assert request_kwargs == {"petId": 9}
