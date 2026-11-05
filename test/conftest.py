"""Keep normal tests isolated from credentials and external services."""

import pytest

from openapi_mcp.config import ServerConfig

LIVE_MODULES = {
    "test_auth.py",
    "test_comprehensive.py",
    "test_fastmcp_server.py",
    "test_fastmcp_live.py",
    "test_mcp_remote_endpoints.py",
    "test_mcp_transport.py",
    "test_server.py",
    "test_sse.py",
    "test_weather.py",
    "test_weather_oslo.py",
}


def pytest_addoption(parser):
    parser.addoption("--run-live-tests", action="store_true", help="Run legacy external-service examples")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.path.name in LIVE_MODULES:
            item.add_marker(pytest.mark.live)
            if not config.getoption("--run-live-tests"):
                item.add_marker(pytest.mark.skip(reason="External-service example; opt in with --run-live-tests"))


@pytest.fixture(autouse=True)
def isolate_configuration(monkeypatch):
    for field in ServerConfig.model_fields.values():
        if field.alias:
            monkeypatch.delenv(field.alias, raising=False)
    monkeypatch.setitem(ServerConfig.model_config, "env_file", None)


@pytest.fixture(autouse=True)
def isolate_working_directory():
    import os

    original = os.getcwd()
    yield
    os.chdir(original)
