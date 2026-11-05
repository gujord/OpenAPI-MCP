"""Unsupported serialization must stop before an upstream request is possible."""

import json
from unittest.mock import Mock

import pytest
from fastmcp import Client

from openapi_mcp.config import ServerConfig
from openapi_mcp.exceptions import OpenAPIError
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer
from openapi_mcp.request_handler import RequestHandler


@pytest.mark.parametrize(
    "operation",
    [
        {"requestBody": {"content": {"application/x-www-form-urlencoded": {"schema": {"type": "object"}}}}},
        {"requestBody": {"content": {"multipart/form-data": {"schema": {"type": "object"}}}}},
        {"requestBody": {"$ref": "#/components/requestBodies/Order"}},
        {
            "parameters": [
                {
                    "name": "tags",
                    "in": "query",
                    "schema": {"type": "array", "items": {"type": "string"}},
                    "explode": False,
                }
            ]
        },
        {"parameters": [{"name": "filter", "in": "query", "schema": {"type": "object"}}]},
        {"parameters": [{"name": "filter", "in": "query", "schema": {"$ref": "#/components/schemas/Filter"}}]},
        {"parameters": [{"$ref": "#/components/parameters/Filter"}]},
        {"parameters": [{"name": "session", "in": "cookie", "schema": {"type": "string"}}]},
        {"parameters": [{"name": "email", "in": "formData", "type": "string"}]},
        {"parameters": [{"name": "value", "in": "path", "style": "matrix", "schema": {"type": "string"}}]},
        {
            "parameters": [
                {"name": "value", "in": "query", "content": {"application/json": {"schema": {"type": "object"}}}}
            ]
        },
        {
            "parameters": [{"name": "payload", "in": "body", "schema": {"type": "object"}}],
            "consumes": ["application/xml"],
        },
    ],
)
async def test_selected_unsupported_operation_stops_startup(tmp_path, operation):
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Unsupported", "version": "1"},
        "servers": [{"url": "https://upstream.example.invalid"}],
        "paths": {
            "/safe": {"get": {"operationId": "safe"}},
            "/value": {"post": {"operationId": "unsupported", **operation}},
        },
    }
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(spec))
    config = ServerConfig(OPENAPI_URL=str(path), MCP_ALLOWED_OPERATIONS=["GET /safe", "POST /value"], _env_file=None)
    server = FastMCPOpenAPIServer(config)
    with pytest.raises(OpenAPIError, match="[Uu]nsupported"):
        await server.initialize()
    async with Client(server.mcp) as client:
        assert await client.list_tools() == []
    # An omitted unsupported route must not prevent a supported route being used.
    config = ServerConfig(OPENAPI_URL=str(path), MCP_ALLOWED_OPERATIONS=["GET /safe"], _env_file=None)
    server = FastMCPOpenAPIServer(config)
    await server.initialize()
    assert [op.operation_id for op in server.operations] == ["safe"]


@pytest.mark.parametrize(
    "location,value",
    [("query", ["a", "b"]), ("query", {"a": 1}), ("header", ["a"]), ("path", {"a": 1}), ("body", None)],
)
def test_ambiguous_values_are_rejected_before_authentication(location, value):
    auth = Mock()
    data, error = RequestHandler(auth).prepare_request(
        1,
        {"value": value},
        [{"name": "value", "in": location, "schema": {}}],
        "/{value}" if location == "path" else "/value",
        "https://upstream.example.invalid",
        "value",
    )
    assert data is None and "error" in error
    auth.add_auth_headers.assert_not_called()
