"""Operation exposure is an explicit, exact allowlist, checked before registration."""

import json
import os
from unittest.mock import Mock

import pytest
from fastmcp import Client
from pydantic import ValidationError
from pydantic_settings import SettingsError

from openapi_mcp.config import ServerConfig
from openapi_mcp.exceptions import ConfigurationError, OpenAPIError
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer


@pytest.fixture
def policy_spec(tmp_path):
    def operation(name):
        return {"operationId": name, "responses": {"200": {"description": "OK"}}}

    spec = {
        "openapi": "3.0.3",
        "info": {"title": "Policy fixture", "version": "1"},
        "servers": [{"url": "https://api.example.invalid"}],
        "paths": {
            "/items": {"get": operation("listItems"), "post": operation("createItem")},
            "/admin/export": {"get": operation("exportPrivateData")},
            "/items/{itemId}": {"delete": operation("deleteItem")},
        },
    }
    path = tmp_path / "api.json"
    path.write_text(json.dumps(spec))
    return path


def make_server(path, **config):
    return FastMCPOpenAPIServer(ServerConfig(OPENAPI_URL=str(path), SERVER_NAME="policy", _env_file=None, **config))


async def test_default_exposes_no_api_operations(policy_spec):
    server = make_server(policy_spec)
    await server.initialize()
    async with Client(server.mcp) as client:
        assert {tool.name for tool in await client.list_tools()} == {"policy_server_info", "policy_list_operations"}
        listing = await client.call_tool("policy_list_operations", {})
        assert listing.data["operations"] == []
        info = await client.call_tool("policy_server_info", {})
        assert info.data["operation_policy"] == "allowlist"


async def test_allowlist_filters_tools_listing_and_prompt_before_any_execution(policy_spec):
    server = make_server(policy_spec, MCP_ALLOWED_OPERATIONS=["GET /items"])
    await server.initialize()
    server.request_handler.prepare_request = Mock(wraps=server.request_handler.prepare_request)
    server.authenticator.add_auth_headers = Mock(side_effect=AssertionError("No credentials for denied calls"))
    async with Client(server.mcp) as client:
        names = {tool.name for tool in await client.list_tools()}
        assert names == {"policy_listItems", "policy_server_info", "policy_list_operations"}
        for name in ("createItem", "exportPrivateData", "deleteItem"):
            result = await client.call_tool(f"policy_{name}", {}, raise_on_error=False)
            assert result.is_error
        server.request_handler.prepare_request.assert_not_called()
        server.authenticator.add_auth_headers.assert_not_called()
        result = await client.call_tool("policy_listItems", {"dry_run": True})
        assert result.data["result"]["request"]["method"] == "GET"
        listing = await client.call_tool("policy_list_operations", {})
        assert [op["operation_id"] for op in listing.data["operations"]] == ["listItems"]
        prompt = await client.get_prompt("policy_api_usage")
        assert "exportPrivateData" not in str(prompt)
        assert "listItems" in str(prompt)


async def test_all_operations_require_explicit_opt_in(policy_spec):
    server = make_server(policy_spec, MCP_OPERATION_POLICY="all")
    await server.initialize()
    assert len(server.operations) == 4


async def test_unknown_selector_stops_startup_without_registering_tools(policy_spec):
    server = make_server(policy_spec, MCP_ALLOWED_OPERATIONS=["GET /items", "GET /typo"])
    with pytest.raises(ConfigurationError, match="GET /typo"):
        await server.initialize()
    async with Client(server.mcp) as client:
        assert await client.list_tools() == []


@pytest.mark.parametrize(
    "settings",
    [
        {"MCP_OPERATION_POLICY": "readonly"},
        {"MCP_OPERATION_POLICY": "all", "MCP_ALLOWED_OPERATIONS": ["GET /items"]},
        {"MCP_ALLOWED_OPERATIONS": ["get /items"]},
        {"MCP_ALLOWED_OPERATIONS": ["GET /items?admin=true"]},
        {"MCP_ALLOWED_OPERATIONS": ["GET /items", "GET /items"]},
        {"MCP_ALLOWED_OPERATIONS": ["DELETE"]},
    ],
)
def test_invalid_or_contradictory_policy_is_rejected(policy_spec, settings):
    with pytest.raises(ValidationError):
        make_server(policy_spec, **settings)


@pytest.mark.parametrize("value", ['["GET /items"]', "not-json", "[true]"])
def test_environment_allowlist_is_a_json_list(policy_spec, monkeypatch, value):
    monkeypatch.setenv("MCP_ALLOWED_OPERATIONS", value)
    if value == '["GET /items"]':
        assert make_server(policy_spec).config.allowed_operations == ["GET /items"]
    else:
        with pytest.raises((ValidationError, SettingsError)):
            make_server(policy_spec)


@pytest.mark.parametrize("ids", [("duplicate", "duplicate"), ("a.b", "a_b"), ("x" * 65, "x" * 64 + "y")])
async def test_tool_name_collisions_fail_instead_of_overwriting_routes(policy_spec, ids):
    spec = json.loads(policy_spec.read_text())
    spec["paths"]["/items"]["get"]["operationId"] = ids[0]
    spec["paths"]["/items"]["post"]["operationId"] = ids[1]
    policy_spec.write_text(json.dumps(spec))
    server = make_server(policy_spec, MCP_OPERATION_POLICY="all")
    with pytest.raises(OpenAPIError, match="collision"):
        await server.initialize()


@pytest.mark.parametrize("name", ["server_info", "list_operations"])
async def test_api_tools_cannot_replace_management_tools(policy_spec, name):
    spec = json.loads(policy_spec.read_text())
    spec["paths"]["/items"]["get"]["operationId"] = name
    policy_spec.write_text(json.dumps(spec))
    with pytest.raises(OpenAPIError, match="reserved"):
        await make_server(policy_spec, MCP_ALLOWED_OPERATIONS=["GET /items"]).initialize()


def test_config_files_do_not_leak_policy_or_credentials_into_other_instances(policy_spec, tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "openapi_url": str(policy_spec),
                "mcp_allowed_operations": ["GET /items"],
                "oauth": {"client_secret": "synthetic-file-secret"},
            }
        )
    )
    before = dict(os.environ)
    config = ServerConfig.from_file(str(config_file))
    assert config.allowed_operations == ["GET /items"]
    assert config.oauth_client_secret == "synthetic-file-secret"
    assert dict(os.environ) == before
    other = ServerConfig(OPENAPI_URL=str(policy_spec), _env_file=None)
    assert other.allowed_operations == []
    assert other.oauth_client_secret is None
    monkeypatch.setenv("MCP_ALLOWED_OPERATIONS", '["POST /items"]')
    assert ServerConfig.from_file(str(config_file)).allowed_operations == ["POST /items"]


async def test_policy_reload_requires_a_new_server_instance(policy_spec):
    server = make_server(policy_spec, MCP_ALLOWED_OPERATIONS=["GET /items"])
    await server.initialize()
    with pytest.raises(RuntimeError, match="new server instance"):
        await server.initialize()


def test_file_dotenv_and_environment_precedence_without_global_mutation(policy_spec, tmp_path, monkeypatch):
    config_file = tmp_path / "settings.json"
    config_file.write_text(json.dumps({"openapi_url": str(policy_spec), "mcp_allowed_operations": ["GET /items"]}))
    dotenv = tmp_path / ".env"
    dotenv.write_text('MCP_ALLOWED_OPERATIONS=["POST /items"]\n')
    monkeypatch.setitem(ServerConfig.model_config, "env_file", str(dotenv))
    assert ServerConfig.from_file(str(config_file)).allowed_operations == ["POST /items"]
    monkeypatch.setenv("MCP_ALLOWED_OPERATIONS", '["GET /admin/export"]')
    assert ServerConfig.from_file(str(config_file)).allowed_operations == ["GET /admin/export"]
