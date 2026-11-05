# Changelog

## Unreleased — 2026-11-05

- Default API exposure to an explicit operation allowlist. An empty list exposes
  no API operations; `MCP_OPERATION_POLICY=all` is an explicit compatibility option.
  Reject unknown selectors, conflicting settings, and tool-name collisions.
- Isolate file configuration from process environment; preserve typed JSON lists
  and environment/.env precedence without leaking credentials between instances.
- Add shared-fixture comparisons with FastMCP's native OpenAPIProvider. Retain the
  current adapter pending validation, preview, and input-shape compatibility work.
- Update examples to select specific operations. This is an intentional behavior
  change for source users; the published PyPI package remains unchanged.


- Prevent server credentials and token acquisition in request previews; stop
  requests after configured token authentication fails.
- Validate and encode path segments; parse comma-separated parameters correctly.
- Disable automatic POST/PATCH retries and bound numeric Retry-After delays.
- Remove full payload/header debug logs in the main request path.
- Update to FastMCP 4 / MCP SDK 2 and expose actual OpenAPI input schemas,
  custom parameter names, JSON bodies, and local schema references.
- Preserve path-level parameters without mutating the source document.
- Use the current HTTP app factory with explicit Host/Origin protection.
  HTTP now defaults to `/mcp`; legacy SSE requires `MCP_TRANSPORT_TYPE=sse`.
- Return schema resources as JSON text; add a process-liveness endpoint and
  meaningful Docker health checks. Publish example Docker ports on loopback.
- Add offline security/functional regressions, isolate test credentials, and
  make returned test values fail instead of silently passing. Legacy live
  examples are explicitly opt-in.
- Refresh setup, security boundaries, and architectural follow-up documentation;
  apply repository source-formatting rules. No package release was made.

Evidence, unresolved limitations, and reproduction commands are recorded in
[the review](docs/reviews/2026-11-05-security-and-compatibility.md).
