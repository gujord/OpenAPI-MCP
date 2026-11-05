"""Offline regression tests for request boundaries and current FastMCP APIs."""

import json
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from openapi_mcp.auth import AuthenticationManager
from openapi_mcp.config import ServerConfig
from openapi_mcp.exceptions import AuthenticationError, ParameterError
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer, OpenAPITool, retry_with_backoff
from openapi_mcp.openapi_loader import OpenAPIParser
from openapi_mcp.request_handler import KwargsParser, PathSanitizer, RequestHandler
from openapi_mcp.schema_converter import NameSanitizer
from openapi_mcp.tool_factory import ToolFunctionFactory


@pytest.fixture
def server(monkeypatch):
    for field in ServerConfig.model_fields.values():
        if field.alias:
            monkeypatch.delenv(field.alias, raising=False)
    return FastMCPOpenAPIServer(ServerConfig(OPENAPI_URL="test/fixtures/petstore.json", _env_file=None))


def operation(method="GET"):
    return OpenAPITool(
        "review",
        method,
        "/items/{id}",
        "Review",
        "Review",
        [
            {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}},
        ],
        "https://api.example.invalid/v1",
    )


@pytest.mark.parametrize("legacy", [False, True])
async def test_dry_run_does_not_fetch_or_disclose_credentials(server, legacy):
    secret = "synthetic-server-owned-secret"
    auth = Mock()
    auth.add_auth_headers.side_effect = lambda headers: {**headers, "X-Custom-Secret": secret}
    server.request_handler = RequestHandler(auth)
    tool = operation()
    if legacy:
        fn = ToolFunctionFactory(server.request_handler, tool.server_url).create_tool_function(
            tool.operation_id, tool.method, tool.path, tool.parameters
        )
        result = fn(id="123", dry_run=True)
    else:
        result = await server._create_tool_function(tool)(id="123", dry_run=True)
    assert result["result"]["dry_run"] is True
    assert secret not in json.dumps(result)
    auth.add_auth_headers.assert_not_called()


@pytest.mark.parametrize("value", [".", "%2e%2e", "%252e%252e", "a%2fb", "a%5cb", "%00", "a\nb"])
def test_encoded_path_navigation_is_rejected(value):
    with pytest.raises(ParameterError):
        PathSanitizer.sanitize_path_parameter(value, "id")


@pytest.mark.parametrize("value", ["item?admin=true", "item#fragment", "blå ost", "email@example.invalid"])
def test_path_values_remain_one_segment(value):
    from urllib.parse import unquote, urlsplit

    handler = RequestHandler(Mock())
    path = handler._replace_path_parameters("/items/{id}", {"id": value}, operation().parameters)
    url = urlsplit("https://api.example.invalid" + path)
    assert not url.query and not url.fragment
    assert unquote(url.path.removeprefix("/items/")) == value
    assert " " not in url.path


def test_comma_separated_parameters_are_not_a_single_query_value():
    assert KwargsParser.parse_kwargs_string("lat=63.1115,lon=7.7327") == {"lat": 63.1115, "lon": 7.7327}


@pytest.mark.parametrize("method,expected_calls", [("POST", 1), ("PATCH", 1), ("GET", 4)])
async def test_retries_do_not_duplicate_non_idempotent_requests(server, method, expected_calls):
    client = AsyncMock()
    client.request.side_effect = httpx.ReadTimeout("response lost")
    with (
        patch("openapi_mcp.fastmcp_server.httpx.AsyncClient") as factory,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        factory.return_value.__aenter__.return_value = client
        result = await server._create_tool_function(operation(method))(id="123")
    assert "error" in result
    assert client.request.await_count == expected_calls


@pytest.mark.parametrize("header", ["999999999", "inf", "nan", "-5"])
async def test_retry_after_cannot_escape_configured_delay_limit(header):
    response = httpx.Response(
        429, headers={"Retry-After": header}, request=httpx.Request("GET", "https://api.example.invalid")
    )
    request = AsyncMock(
        side_effect=[httpx.HTTPStatusError("limited", request=response.request, response=response), "ok"]
    )
    with patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
        assert await retry_with_backoff(request, max_retries=1, max_delay=2) == "ok"
    assert 0 <= sleep.call_args.args[0] <= 2


@pytest.mark.parametrize("transport", ["http", "sse"])
def test_app_factories_use_supported_fastmcp_api(server, transport):
    app = server.get_http_app() if transport == "http" else server.get_sse_app()
    assert callable(app)


def test_parser_inherits_path_parameters_without_mutating_spec():
    spec = {
        "paths": {
            "/items/{itemId}": {
                "parameters": [{"name": "itemId", "in": "path", "required": True, "schema": {"type": "string"}}],
                "post": {
                    "operationId": "create",
                    "requestBody": {"required": True, "content": {"application/json": {"schema": {"type": "object"}}}},
                },
            }
        }
    }
    snapshot = json.dumps(spec, sort_keys=True)
    parser = OpenAPIParser(NameSanitizer.sanitize_name)
    first = parser.parse_operations(spec)["create"]["parameters"]
    second = parser.parse_operations(spec)["create"]["parameters"]
    assert [p["name"] for p in first] == ["itemId", "body"]
    assert first == second
    assert json.dumps(spec, sort_keys=True) == snapshot


async def test_real_mcp_client_can_send_custom_parameters_and_json_body(server):
    from fastmcp import Client

    server.openapi_spec = {
        "components": {
            "schemas": {
                "Order": {
                    "type": "object",
                    "properties": {"quantity": {"type": "integer", "minimum": 1}},
                    "required": ["quantity"],
                }
            }
        }
    }
    tool = OpenAPITool(
        "createOrder",
        "POST",
        "/customers/{customerId}/orders",
        "Create",
        "Create",
        [
            {"name": "customerId", "in": "path", "required": True, "schema": {"type": "string"}},
            {"name": "X-Trace", "in": "header", "schema": {"type": "string"}},
            {"name": "body", "in": "body", "required": True, "schema": {"$ref": "#/components/schemas/Order"}},
        ],
        "https://api.example.invalid",
    )
    server._register_single_tool(tool)
    server._register_resources()
    name = f"{server.config.server_name}_createOrder"
    async with Client(server.mcp) as client:
        resources = await client.list_resources()
        resource = await client.read_resource(resources[0].uri)
        assert json.loads(resource[0].text)["type"] == "object"
        tools = await client.list_tools()
        assert len(tools) == 1
        result = await client.call_tool(
            name, {"customerId": "c1", "X-Trace": "trace", "body": {"quantity": 2}, "dry_run": True}
        )
        request = result.data["result"]["request"]
        assert request["url"] == "https://api.example.invalid/customers/c1/orders"
        assert request["body"] == {"quantity": 2}
        assert request["headers"]["X-Trace"] == "trace"
        invalid = await client.call_tool(
            name, {"customerId": "c1", "body": {"quantity": 0}, "dry_run": True}, raise_on_error=False
        )
        assert invalid.is_error


async def test_untrusted_origin_is_rejected_before_http_tool_execution(server):
    app = server.get_http_app()
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
        ) as client:
            response = await client.post("/mcp", headers={"Origin": "https://untrusted.example.invalid"}, json={})
            allowed = await client.post("/mcp", headers={"Origin": "http://localhost:3000"}, json={})
            bad_host = await client.post("/mcp", headers={"Host": "untrusted.example.invalid"}, json={})
            health = await client.get("/health")
    assert response.status_code == 403
    assert allowed.status_code not in {403, 421}
    assert bad_host.status_code == 421
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


async def test_debug_logging_does_not_include_headers_inputs_or_response_values(server, caplog):
    server.config.debug = True
    secret = "synthetic-private-value"
    server.authenticator.add_auth_headers = lambda headers: {**headers, "X-Tenant-Secret": secret}
    response = httpx.Response(
        200,
        json={"private": secret},
        headers={"Set-Cookie": secret},
        request=httpx.Request("GET", "https://api.example.invalid"),
    )
    client = AsyncMock()
    client.request.return_value = response
    with patch("openapi_mcp.fastmcp_server.httpx.AsyncClient") as factory, caplog.at_level("DEBUG"):
        factory.return_value.__aenter__.return_value = client
        result = await server._create_tool_function(operation())(id=secret)
    assert result["result"]["data"]["private"] == secret
    assert secret not in caplog.text


def test_oauth_uses_the_supplied_config_and_stops_after_failure(server, caplog):
    config = ServerConfig(
        OPENAPI_URL="test/fixtures/petstore.json",
        OAUTH_CLIENT_ID="configured-client",
        OAUTH_CLIENT_SECRET="configured-secret",
        OAUTH_TOKEN_URL="https://auth.example.invalid/token",
        _env_file=None,
    )
    manager = AuthenticationManager(config)
    response = httpx.Response(401, text="configured-secret", request=httpx.Request("POST", config.oauth_token_url))
    with patch("openapi_mcp.auth.httpx.post", return_value=response) as post, caplog.at_level("DEBUG"):
        with pytest.raises(AuthenticationError):
            manager.add_auth_headers({})
    assert post.call_args.kwargs["data"]["client_id"] == "configured-client"
    assert "configured-secret" not in caplog.text


def test_failed_authentication_never_prepares_an_anonymous_request(server):
    auth = Mock()
    auth.add_auth_headers.side_effect = AuthenticationError("private provider diagnostic")
    data, error = RequestHandler(auth).prepare_request(
        1, {"id": "123"}, operation().parameters, "/items/{id}", "https://api.example.invalid", "getItem"
    )
    assert data is None and error["error"]["code"] == -32603
    assert "private provider diagnostic" not in json.dumps(error)
