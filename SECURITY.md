# Security policy

## Deployment boundary

OpenAPI-MCP executes API operations with the credentials configured on the
server. Those credentials do **not** authenticate MCP clients. The current
executable has an operation allowlist that defaults to no API operations.
There is still no per-user authorization. The explicit `all` policy opts into
every operation in the trusted specification.

Use stdio for a client-owned local process, or bind HTTP to loopback. Before
making HTTP accessible to other machines, provide client authentication and
access controls appropriate to the deployment. Host/Origin validation helps
against unwanted browser requests and host rebinding; it does not establish a
client's identity. CORS is not an authorization mechanism.

Only load trusted OpenAPI documents and trusted upstream URLs. A document
controls request destinations, tool descriptions, and available operations.
Custom authentication headers are also used when fetching a remote document.
Do not let an untrusted party choose that URL or edit the specification. API
responses and descriptions may contain hostile instructions for an AI client;
the proxy does not sanitize prompt injection.

Use least-privilege upstream credentials and HTTPS for remote API/token URLs.
The service does not yet enforce destination allowlists, remote document/response
size limits, or complete OpenAPI serialization semantics. Debug logs and error
messages are not a general-purpose secret redactor: dependencies, URLs, and
upstream error bodies may still contain sensitive data.

## Operation policy

`MCP_ALLOWED_OPERATIONS` contains exact `METHOD /path` selectors. Unknown entries
and contradictory settings stop startup. Omitted operations are never registered
as tools; knowing an operation name does not bypass the policy. Names that collide
after sanitization are rejected. The policy is fixed at startup and applies to
all clients of that server. Metadata resources remain available; the allowlist
is a request-execution boundary, not a confidentiality filter for the document.

File-based configuration no longer writes policy or credentials into process-wide
environment variables. See the [policy and adapter review](docs/reviews/2026-11-05-operation-policy-and-adapters.md)
for tests and the limitations of a possible native-provider migration.

## Unreleased hardening

The local November 2026 review adds:

- Request previews that do not fetch tokens or include server-injected credentials.
- Encoded path-segment validation and quoting before URL construction.
- No automatic retries for POST/PATCH; bounded numeric Retry-After delays.
- Fail-closed behavior when configured token authentication fails.
- Explicit FastMCP Host/Origin protection and loopback-only Docker port mappings.
- Request/response debug metadata without full headers or payloads.
- Offline regression tests and current FastMCP/MCP dependency constraints.

These changes are **not included in PyPI 1.0.4**. They have not undergone an
independent human security audit. Automated checks and an empty dependency-audit
result are limited evidence, not a certification that the software is secure.
See the [review record](docs/reviews/2026-11-05-security-and-compatibility.md).

Deprecated server/transport modules remain in the source tree; use the
`openapi-mcp` executable (`fastmcp_server.py`). Runtime dependencies should be
resolved and audited for the actual deployment. The repository's h11/httpcore
minimums address earlier dependency updates, not every possible HTTP issue.

## Reporting

Do not publish exploit details, credentials, or sensitive logs in a public issue.
Send a private report to the maintainer at [roger@gujord.no](mailto:roger@gujord.no)
with affected versions, a minimal reproduction using synthetic data, expected
and observed behavior, and the likely impact. Public issues are appropriate for
non-sensitive bugs. No response-time guarantee is currently offered.
