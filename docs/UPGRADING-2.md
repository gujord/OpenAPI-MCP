# Upgrading from 1.0.4 to 2.0

`2.0.0rc1` is a release candidate. Install it explicitly in a new environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install 'openapi-mcp-proxy==2.0.0rc1'
```

Python 3.10 or later is required. This version targets FastMCP 4 and MCP SDK 2.
The candidate includes security fixes and intentional compatibility changes;
retain the old environment/configuration until the candidate works for your API.

## Select API operations

The default now exposes **no API operations**. Select exact method/path pairs
from the OpenAPI document, without its base URL:

```bash
OPENAPI_URL='./api.json' \
MCP_ALLOWED_OPERATIONS='["GET /items", "POST /orders"]' \
openapi-mcp
```

The environment value is a JSON array. Unknown paths, invalid settings, or
colliding tool names stop startup. To explicitly restore the old broad exposure,
use `MCP_OPERATION_POLICY=all` and unset `MCP_ALLOWED_OPERATIONS`. This is not a
per-user permission system; every connected client gets the selected tools.

## Update HTTP clients

With `MCP_HTTP_ENABLED=true`, clients now connect to `/mcp`. To retain the legacy
`/sse` endpoint, explicitly set `MCP_TRANSPORT_TYPE=sse`.

HTTP Host and Origin checks are enabled. For a trusted non-local deployment,
configure `MCP_ALLOWED_HOSTS` and `MCP_CORS_ORIGINS` for its actual values.
These checks do not authenticate clients. Upstream OAuth credentials/API keys
still authorize outgoing API requests, not incoming MCP access.

## Update tool calls

Arguments now follow the OpenAPI names and supported JSON Schema constraints.
Use the API's actual parameter names instead of a generic `kwargs` wrapper.
JSON request bodies use the `body` argument:

```json
{"customerId": "c1", "body": {"quantity": 2}, "dry_run": true}
```

`dry_run`, `req_id`, and `kwargs` are reserved names. Required inputs and
constraints such as minimum values are checked. Dry runs do not obtain tokens or
include server-injected credentials. Caller-supplied data remains visible.
Configured token authentication failures stop the request. POST/PATCH calls are
no longer retried automatically after an error or timeout.

## Supported request subset

The current adapter supports scalar path/query/header parameters and directly
declared JSON request bodies, including local schema component references.
Selected operations requiring form/multipart/XML bodies, array/object non-body
parameters, parameter references/content, cookie parameters, or nondefault
serialization styles are rejected at startup. Remove those operations from the
allowlist or adapt the specification/API; do not disguise their types to bypass
the check. Unsupported operations omitted from the allowlist may remain in the
same document. Explicit null JSON bodies are rejected before authentication.

This is a restricted adapter, not a complete OpenAPI implementation. The native
FastMCP adapter is being evaluated separately and is not the default here.

## Package and publication checks

The release workflow runs the offline tests, builds distributions, validates
metadata with Twine, then installs the wheel in a clean environment. That exact
wheel must pass actual stdio and loopback HTTP tool calls before upload. The test
uses only a local synthetic API, including denied operations, invalid bodies,
credential-free previews, schema reads, and Host/Origin rejection.

GitHub publishes through PyPI Trusted Publishing. Configure the existing PyPI
project with owner `gujord`, repository `OpenAPI-MCP`, workflow `publish.yml`,
and no environment name. Do not paste a PyPI token into an issue or chat.

Existing static typing debt and the eleven opt-in legacy live examples remain
outside the passing release tests. Docker and arbitrary external clients have
not been validated by this release procedure.
