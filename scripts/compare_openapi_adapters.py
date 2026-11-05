"""Compare captured requests against shared expectations without using a network.

Run from the repository root. A nonzero exit means at least one adapter does
not meet an expectation; findings are not converted into passing tests.
"""

import argparse
import asyncio
import json
import re
import socket
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qsl, urlsplit

import httpx
import httpx2
from fastmcp import Client, FastMCP
from fastmcp.server.providers.openapi import MCPType, RouteMap

from openapi_mcp.config import ServerConfig
from openapi_mcp.fastmcp_server import FastMCPOpenAPIServer

SPEC_PATH = Path(__file__).resolve().parents[1] / "test/fixtures/adapter-conformance.json"
ALLOWED = ["GET /items/{itemId}", "POST /orders", "GET /search", "POST /submit", "GET /fail"]
CASES = [
    ("path-query-header", "getItem", {"itemId": "a b", "limit": 2, "X-Trace": "trace"}, None),
    ("json-local-reference", "createOrder", {"body": {"quantity": 2, "sku": "item"}}, {"quantity": 2, "sku": "item"}),
    ("csv-query-array", "search", {"tags": ["alpha", "beta"]}, None),
    ("form-body", "submitForm", {"body": {"email": "test@example.invalid"}}, {"email": "test@example.invalid"}),
    ("invalid-body-rejected", "createOrder", {"body": {"quantity": 0, "sku": "item"}}, {"quantity": 0, "sku": "item"}),
    ("dry-run", "getItem", {"itemId": "a", "dry_run": True}, None),
    ("denied-operation", "deletePrivate", {}, None),
    ("upstream-error", "fail", {}, None),
]


def normalize(request):
    parts = urlsplit(str(request.url))
    body = request.content.decode()
    return {
        "method": request.method,
        "path": parts.path,
        "query": parse_qsl(parts.query),
        "trace": request.headers.get("X-Trace"),
        "content_type": request.headers.get("content-type", ""),
        "body": json.loads(body) if "application/json" in request.headers.get("content-type", "") else body,
    }


def meets_expectation(name, result, requests):
    if name in {"invalid-body-rejected", "denied-operation"}:
        return result.is_error and not requests
    if name == "dry-run":
        return not result.is_error and not requests
    if name == "upstream-error":
        return result.is_error and len(requests) == 1
    if result.is_error or len(requests) != 1:
        return False
    request = requests[0]
    if name == "path-query-header":
        return (
            request["method"] == "GET"
            and request["path"] == "/items/a%20b"
            and request["query"] == [("limit", "2")]
            and request["trace"] == "trace"
        )
    if name == "json-local-reference":
        return request["method"] == "POST" and request["body"] == {"quantity": 2, "sku": "item"}
    if name == "csv-query-array":
        return request["query"] == [("tags", "alpha,beta")]
    if name == "form-body":
        return request["content_type"].startswith("application/x-www-form-urlencoded") and parse_qsl(
            request["body"]
        ) == [("email", "test@example.invalid")]
    raise AssertionError(name)


async def compare(adapter, case):
    name, operation, custom_args, native_args = case
    requests = []
    http = httpx if adapter == "custom" else httpx2

    def handle(request):
        requests.append(normalize(request))
        status = 503 if request.url.path == "/fail" else 200
        return http.Response(status, json={"ok": status == 200})

    spec = json.loads(SPEC_PATH.read_text())
    async with http.AsyncClient(base_url=spec["servers"][0]["url"], transport=http.MockTransport(handle)) as upstream:
        with ExitStack() as stack:
            if adapter == "custom":
                config = ServerConfig(
                    OPENAPI_URL=str(SPEC_PATH),
                    SERVER_NAME="comparison",
                    MCP_OPERATION_POLICY="allowlist",
                    MCP_ALLOWED_OPERATIONS=ALLOWED,
                    HTTP_MAX_RETRIES=0,
                    MCP_AUTH_HEADERS="",
                    OAUTH_CLIENT_ID=None,
                    OAUTH_CLIENT_SECRET=None,
                    OAUTH_TOKEN_URL=None,
                    API_USERNAME=None,
                    API_PASSWORD=None,
                    _env_file=None,
                )
                server = FastMCPOpenAPIServer(config)
                await server.initialize()
                mcp, tool_name, arguments = server.mcp, f"comparison_{operation}", custom_args
                # The production request path receives an actual mock HTTP client.
                stack.enter_context(
                    patch(
                        "openapi_mcp.fastmcp_server.httpx.AsyncClient",
                        return_value=AsyncMock(
                            __aenter__=AsyncMock(return_value=upstream), __aexit__=AsyncMock(return_value=False)
                        ),
                    )
                )
            else:
                maps = [
                    RouteMap(
                        methods=[selector.split(" ", 1)[0]],
                        pattern="^" + re.escape(selector.split(" ", 1)[1]) + "$",
                        mcp_type=MCPType.TOOL,
                    )
                    for selector in ALLOWED
                ]
                maps.append(RouteMap(mcp_type=MCPType.EXCLUDE))
                mcp = FastMCP.from_openapi(spec, client=upstream, route_maps=maps, strict_input_validation=True)
                tool_name, arguments = operation, custom_args if native_args is None else native_args
            async with Client(mcp) as client:
                listed = {tool.name: tool for tool in await client.list_tools()}
                result = await client.call_tool(tool_name, arguments, raise_on_error=False)
                fields = sorted(listed[tool_name].input_schema.get("properties", {})) if tool_name in listed else []
                return {
                    "adapter": adapter,
                    "case": name,
                    "pass": meets_expectation(name, result, requests),
                    "is_error": result.is_error,
                    "requests": requests,
                    "input_fields": fields,
                }


async def run():
    return [await compare(adapter, case) for adapter in ("custom", "native") for case in CASES]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    original_connect = socket.socket.connect

    def local_only(sock, address):
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            raise RuntimeError("Network access is disabled in the adapter comparison")
        return original_connect(sock, address)

    with patch.object(socket.socket, "connect", local_only):
        results = asyncio.run(run())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    for result in results:
        print(f"{result['adapter']:6} {result['case']:24} {'PASS' if result['pass'] else 'GAP'}")
    return int(any(not result["pass"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
