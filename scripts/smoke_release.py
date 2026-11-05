"""Exercise an installed wheel through real stdio and loopback HTTP transports.

Run with a clean virtual environment containing the built wheel. Only synthetic
credentials and a loopback upstream API are used. No public service is called.
"""

import argparse
import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import distribution, version
from pathlib import Path

import httpx
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

import openapi_mcp

SECRET = "synthetic-release-smoke-secret"


async def exercise(client, requests):
    async with client:
        names = {tool.name for tool in await client.list_tools()}
        assert names == {"smoke_getItem", "smoke_createItem", "smoke_server_info", "smoke_list_operations"}, names
        count = len(requests)
        preview = await client.call_tool("smoke_getItem", {"itemId": "a b", "dry_run": True})
        assert preview.data["result"]["request"]["url"].endswith("/items/a%20b")
        assert SECRET not in json.dumps(preview.data) and len(requests) == count
        invalid = await client.call_tool("smoke_createItem", {"body": {"quantity": 0}}, raise_on_error=False)
        assert invalid.is_error and len(requests) == count
        denied = await client.call_tool("smoke_deleteItem", {}, raise_on_error=False)
        assert denied.is_error and len(requests) == count
        result = await client.call_tool("smoke_getItem", {"itemId": "a b", "limit": 2, "X-Trace": "trace"})
        assert result.data["result"]["status_code"] == 200
        assert requests[-1] == {
            "method": "GET",
            "path": "/items/a%20b?limit=2",
            "trace": "trace",
            "auth": SECRET,
            "body": None,
        }
        result = await client.call_tool("smoke_createItem", {"body": {"quantity": 2}})
        assert result.data["result"]["data"] == {"received": {"quantity": 2}}
        assert requests[-1]["auth"] == SECRET and len(requests) == count + 2
        resources = await client.list_resources()
        assert resources
        resource = await client.read_resource(resources[0].uri)
        assert json.loads(resource[0].text)["type"] == "object"


async def run(executable, work, spec_path, requests):
    env = {key: value for key, value in os.environ.items() if key in {"PATH", "SYSTEMROOT", "WINDIR", "TMPDIR", "LANG"}}
    env.update(
        {
            "OPENAPI_URL": str(spec_path),
            "SERVER_NAME": "smoke",
            "MCP_AUTH_HEADERS": json.dumps({"X-API-Key": SECRET}),
            "MCP_ALLOWED_OPERATIONS": json.dumps(["GET /items/{itemId}", "POST /items"]),
            "HTTP_MAX_RETRIES": "0",
        }
    )
    transport = StdioTransport(str(executable), args=[], env=env, cwd=str(work), log_file=work / "stdio.log")
    await exercise(Client(transport, timeout=10), requests)
    print("PASS: installed console command over stdio", flush=True)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    http_env = {**env, "MCP_HTTP_ENABLED": "true", "MCP_HTTP_HOST": "127.0.0.1", "MCP_HTTP_PORT": str(port)}
    with (work / "http.log").open("w") as log:
        process = subprocess.Popen([str(executable)], cwd=work, env=http_env, stdout=log, stderr=log)
        try:
            url = f"http://127.0.0.1:{port}"
            async with httpx.AsyncClient(trust_env=False) as http:
                for _ in range(100):
                    if process.poll() is not None:
                        raise RuntimeError("HTTP server exited: " + (work / "http.log").read_text())
                    try:
                        response = await http.get(url + "/health", timeout=0.5)
                        if response.status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    await asyncio.sleep(0.1)
                else:
                    raise TimeoutError("HTTP server did not become ready")
                blocked = await http.post(
                    url + "/mcp", headers={"Origin": "https://untrusted.example.invalid"}, json={}
                )
                assert blocked.status_code == 403
                blocked = await http.post(url + "/mcp", headers={"Host": "untrusted.example.invalid"}, json={})
                assert blocked.status_code == 421
            await exercise(Client(url + "/mcp", timeout=10), requests)
            print("PASS: installed console command over HTTP, including Host/Origin rejection", flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    expected = re.search(r'^version = "([^"]+)"$', (root / "pyproject.toml").read_text(), re.MULTILINE).group(1)
    assert version("openapi-mcp-proxy") == openapi_mcp.__version__ == expected
    direct_url = json.loads(distribution("openapi-mcp-proxy").read_text("direct_url.json") or "{}")
    assert not direct_url.get("dir_info", {}).get("editable"), "Use an installed wheel, not an editable checkout"
    assert (
        Path(openapi_mcp.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
    ), "Package must be in the test environment"
    executable = Path(sys.executable).with_name("openapi-mcp.exe" if os.name == "nt" else "openapi-mcp")
    requests = []

    class Upstream(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond(None)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.respond(body)

        def respond(self, body):
            requests.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "trace": self.headers.get("X-Trace"),
                    "auth": self.headers.get("X-API-Key"),
                    "body": body,
                }
            )
            data = json.dumps({"received": body}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format, *args):
            return

    api = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
    worker = threading.Thread(target=api.serve_forever, daemon=True)
    worker.start()
    try:
        with tempfile.TemporaryDirectory(prefix="openapi-mcp-release-") as directory:
            work = Path(directory)
            spec = {
                "openapi": "3.0.3",
                "info": {"title": "Wheel smoke", "version": "1"},
                "servers": [{"url": f"http://127.0.0.1:{api.server_port}"}],
                "paths": {
                    "/items/{itemId}": {
                        "get": {
                            "operationId": "getItem",
                            "parameters": [
                                {"name": "itemId", "in": "path", "required": True, "schema": {"type": "string"}},
                                {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                                {"name": "X-Trace", "in": "header", "schema": {"type": "string"}},
                            ],
                        },
                        "delete": {"operationId": "deleteItem"},
                    },
                    "/items": {
                        "post": {
                            "operationId": "createItem",
                            "requestBody": {
                                "required": True,
                                "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Item"}}},
                            },
                        }
                    },
                },
                "components": {
                    "schemas": {
                        "Item": {
                            "type": "object",
                            "properties": {"quantity": {"type": "integer", "minimum": 1}},
                            "required": ["quantity"],
                        }
                    }
                },
            }
            spec_path = work / "api.json"
            spec_path.write_text(json.dumps(spec))
            asyncio.run(run(executable, work, spec_path, requests))
    finally:
        api.shutdown()
        api.server_close()
        worker.join(timeout=5)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"version": expected, "stdio": "PASS", "http": "PASS", "upstream_requests": len(requests)}, indent=2)
        + "\n"
    )
    print(f"PASS: {expected}, {len(requests)} permitted upstream requests, no external services", flush=True)


if __name__ == "__main__":
    main()
