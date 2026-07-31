# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Roger Gujord
# https://github.com/gujord/OpenAPI-MCP

"""Regression tests for supported FastMCP transport APIs."""

from typing import Any, Dict, List, Tuple

import pytest

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


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
    setattr(server, "mcp", recorder)

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
        ("run_http_async", "http"),
        ("run_sse_async", "sse"),
    ],
)
async def test_async_transport_runners_delegate_to_fastmcp(run_method: str, expected_transport: str) -> None:
    """Delegate asynchronous transport startup to FastMCP."""
    server = make_server()
    recorder = TransportRecorder()
    setattr(server, "mcp", recorder)

    await getattr(server, run_method)(host="0.0.0.0", port=8123)

    assert recorder.calls == [(expected_transport, {"host": "0.0.0.0", "port": 8123})]
