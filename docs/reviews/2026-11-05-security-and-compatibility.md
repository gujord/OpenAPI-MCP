# Security, functionality, and compatibility review — 2026-11-05

Subsequent operation-policy work and the completed adapter comparison are recorded
in [the follow-up review](2026-11-05-operation-policy-and-adapters.md). Results
below describe the initial phase and are preserved as that phase's record.

## Scope and evidence

Roger requested a review and improvements to his OpenAPI-MCP project, including
recent ecosystem developments. This work uses a local branch,
`fix/security-functionality-review-20261105`, based on public main commit
`721ba12e05234484074afcbe4d9897c3ddc6a986`. PyPI's latest stable
`openapi-mcp-proxy` version was 1.0.4 at inspection. There were no GitHub release
or tag entries at that time. No changes were pushed or released.

The review covered the primary FastMCP entry point, request construction,
authentication, parsing, tests, dependency compatibility, and deployment examples.
It did not include attacking deployed services or using real API credentials.
Findings were reproduced with synthetic data and local tests. The analysis and
patches were AI-assisted; this is not an independent human security audit.

## Confirmed findings and changes

| Area | Previous behavior | Change and evidence |
| --- | --- | --- |
| Request previews | Added server-owned headers and could fetch a token before returning a dry run | Skip authentication in previews; regression covers both primary and legacy request preparation |
| Path inputs | Encoded traversal bypassed raw checks; `?` and `#` could change URL structure | Check bounded decoded forms and percent-encode the original value as a single segment |
| Retries | POST/PATCH could execute repeatedly after a timeout or retryable response | Restrict automatic retries to idempotent methods; tests count attempts after a lost response |
| Retry delays | Arbitrarily large/non-finite Retry-After values reached sleep | Validate and clamp numeric delays; invalid values use bounded backoff |
| Authentication | OAuth ignored the supplied config; failed token methods could fall through to anonymous requests | Use the supplied config, preserve successful configured fallback, and stop after all configured token methods fail |
| Debug logging | Main request path logged full headers, bodies, and response values | Log operation/status/size metadata; test uses synthetic secrets |
| Tool arguments | Fixed Python signature hid arbitrary API fields and JSON bodies | Register a schema-backed tool, validate arguments, preserve local component references, reject ambiguous/reserved names |
| Parameter parsing | Comma-separated values could be read as one query value; path-level parameters were ignored; parsing mutated the input document | Reorder parsing, inherit/override parameters by name and location, deep-copy operations |
| Transport | Removed FastMCP app methods; HTTP option defaulted to SSE | Use current `http_app`, explicit Host/Origin validation, and `/mcp` by default |
| Resources and health | JSON resource function returned a dictionary despite its text contract; Docker health checks accepted errors and no primary health route existed | Return JSON text; add `/health`; fail health checks on HTTP errors |
| Test reliability | Several tests swallowed exceptions and returned booleans, which pytest treated as success | Convert offline examples to assertions, fail on returned test values, and separate live examples |

Credential disclosure severity depends on who can invoke tools and whether the
upstream credential grants more access than the exposed operations. Path handling
impact depends on upstream routing/decoding. These are reproduced defects and
hardening changes, not claims of demonstrated compromise of a deployed service.
Logging changes are limited to the reviewed paths: upstream responses, error
messages, dependency logs, and configured URLs can still contain sensitive data.

The first 25 regression cases produced **23 failures and 2 passes** before the
initial fixes. Two later authentication regressions also failed before their
fixes. The completed regression file contains 29 cases. Host/Origin behavior is
checked through an in-memory ASGI client; tools, schemas, bodies, and resource
reads are exercised through FastMCP's in-process MCP client.

## Validation performed

Local evidence is in the ignored directory `build/review-20261105/`. It is not a
published artifact. The retained logs distinguish initial failures from final
runs; no receipt was relabeled as a new run.

| Check | Result |
| --- | --- |
| Python 3.12.9 offline suite | 152 passed, 11 skipped |
| Python 3.10.4 offline suite | 152 passed, 11 skipped |
| Python 3.12 suite with UserWarning promoted to error | 152 passed, 11 skipped |
| Black, isort, flake8 on source | Passed |
| Bandit on source, existing project configuration | No findings |
| pip-audit on the installed Python 3.12 environment | No known vulnerabilities found at audit time |
| Source and wheel build | Passed; version remains 1.0.4 locally, not a release |
| Mypy, same environment and command | 85 errors in original source; 76 in modified source; still failing |

The environment used **FastMCP 4.1.6**, **mcp 2.3.0**, **jsonschema 4.26.0**, and
**referencing 0.37.0**. Exact Python 3.12 environment versions are retained in
`resolved-dependencies.txt`; the environment includes development tools.
The dependency scan is not a proof that all versions allowed by the manifest
are safe. Runtime requirements now constrain FastMCP and mcp to their tested
major versions, while still allowing compatible minor updates.

One collection warning comes from a retained deprecated-server example. An
intermittent blocked-socket warning occurred during an in-process client test;
the full warnings-as-errors rerun passed. Network sockets remained blocked.
The eleven live examples were not executed and are not counted as validated
compatibility. They still need migration before becoming a reliable live gate.
Docker builds, other operating systems, external clients, and production HTTP
deployments were not tested. Static typing remains a recorded backlog, not a
passed check; the existing optional CI type-check setting was not weakened.

Commands used for the final checks, from the repository root:

```bash
build/review-20261105/venv/bin/python -m pytest test/ -q
build/review-20261105/venv/bin/python -m pytest test/ -q -W error::UserWarning
build/review-20261105/venv310/bin/python -m pytest test/ -q
build/review-20261105/venv/bin/black --check src/openapi_mcp test/test_security_regressions.py test/conftest.py
build/review-20261105/venv/bin/isort --check-only src/openapi_mcp test/test_security_regressions.py test/conftest.py
build/review-20261105/venv/bin/flake8 src/openapi_mcp --max-line-length=120 --ignore=E501,W503,E203
build/review-20261105/venv/bin/bandit -r src/openapi_mcp -c pyproject.toml
build/review-20261105/venv/bin/pip-audit --local
build/review-20261105/venv/bin/mypy src/openapi_mcp --ignore-missing-imports
build/review-20261105/venv/bin/python -m build --outdir build/review-20261105/dist
git diff --check
```

A clean original `src/` was exported from HEAD into `baseline-source/` for the
Mypy comparison. Source imports/formatting were normalized to the repository's
existing CI rules. Bandit's earlier LOW findings for retry jitter were addressed
with SystemRandom; unpredictability of retry jitter was not itself classified
as an exploitable defect. A legacy empty exception handler now logs disconnect
failure instead of silently passing.

## Recent ecosystem developments

Primary sources were consulted on 5 November 2026:

- [MCP 2026-07-28 transport specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports)
  specifies stdio and Streamable HTTP, per-request protocol metadata, and
  compatibility handling for earlier revisions. That changes the basis for
  claims about complete compliance. This patch delegates transport to current
  FastMCP; it does not independently establish every protocol requirement.
- [FastMCP OpenAPI integration](https://gofastmcp.com/integrations/openapi) provides
  `from_openapi` (introduced in v2), backed by OpenAPIProvider from v3, with route
  selection/exclusion and broader parameter/body support. The feature is not
  newly invented in 2026. The current implementation is relevant to replacing
  duplicated conversion logic here. The maintainers also recommend curated
  tools over exposing a large API indiscriminately.
- [FastMCP HTTP deployment](https://gofastmcp.com/deployment/http) describes the
  current app factory and deployment configuration. The installed 4.1.6 source
  was also inspected; protection is explicitly enabled by this application.
- [PyPI project metadata](https://pypi.org/project/openapi-mcp-proxy/) and the
  FastMCP/mcp package metadata were checked before selecting stable dependencies.

## Recommended next work

1. **Operation policy and a native-provider comparison.** Build shared fixtures
   for the current adapter and FastMCP's native OpenAPIProvider. Cover path/query
   serialization, bodies, local references, tool naming, dry runs, and errors.
   Add an explicit allowlist with a deny-by-default profile; a method-only
   read-only profile is not sufficient for APIs that misuse GET. Retain only
   useful project-specific behavior when deciding whether to switch converters.
2. **Incoming MCP authentication.** Use the framework's maintained auth support
   for remote deployments, with per-user operation policy and separate upstream
   identities where required. Do not confuse CORS or upstream OAuth with client
   authorization. Test authorization failures before real API execution.
3. **Bounded resources and asynchronous I/O.** Limit remote document and response
   sizes, validate trusted destinations, avoid synchronous token/spec loading
   on the async event loop, and reuse appropriately scoped HTTP clients.
4. **Conformance and retirement of legacy code.** Test an actual stdio subprocess
   and HTTP client/server exchange against supported revisions; migrate live
   examples; resolve typing errors; remove deprecated custom transport modules
   in a deliberate compatibility change.

Further known gaps include external/path-item/parameter references, non-JSON
bodies, general OpenAPI serialization, operation-name collisions, configuration
file loading that mutates environment variables, and upstream error redaction.
No claim of full OpenAPI or MCP conformance, safe multi-tenant deployment, or
an exhaustive vulnerability assessment follows from this first review.

## Handoff

The code, tests, README, security guidance, and change log are ready for local
review on the named branch. Public main and PyPI remain unchanged. Before a
release, choose a new version, review the compatibility changes (HTTP endpoint,
input schemas, auth failure behavior, and POST/PATCH retries), and complete the
network/container checks appropriate to the intended deployment.
