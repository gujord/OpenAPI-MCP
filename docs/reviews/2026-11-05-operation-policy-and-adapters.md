# Operation policy and adapter comparison — 2026-11-05

## Outcome

The primary server now exposes API operations only through an explicit allowlist.
The default empty list exposes no API operations. `MCP_OPERATION_POLICY=all`
restores broad exposure deliberately. This is an intentional compatibility change
for source installations; the PyPI package has not been released again.

A shared-fixture comparison supports evaluating FastMCP's native OpenAPIProvider
as a future replacement, but not switching directly. It correctly serializes two
request forms that our adapter does not support. Our preview and input-validation
contracts need additional implementation around that provider.

This follows the [initial review](2026-11-05-security-and-compatibility.md).
Roger authorized continued work and subsequently requested pushing the combined
changes to remote `main`. No deployment or PyPI release was requested.

## Operation boundary

- `MCP_ALLOWED_OPERATIONS` is a JSON array of exact uppercase `METHOD /path`
  selectors. The path is taken from the OpenAPI document, excluding its server
  base URL. No wildcards or regular expressions are interpreted.
- Unknown selectors, duplicates, malformed values, and `all` combined with a
  nonempty allowlist fail configuration/startup. Selection happens before tool
  registration, authentication, or API execution.
- Only permitted operations appear in tool discovery, operation listings, and
  generated usage examples. Calling an omitted tool by name returns an error
  without entering request preparation.
- Operation-name collisions after sanitization/truncation are rejected. Allowed
  API operations cannot use the reserved management names `server_info` or
  `list_operations`.
- The policy applies to every client of an instance. Reinitializing an existing
  server is rejected; use a new instance to change policy or specification.
- Information tools and schema resources remain available. Descriptions and
  component schemas are not redacted. This controls execution, not access to
  every piece of metadata in the document.

There is still no per-user MCP authentication/authorization, API destination
allowlist, or assurance that an allowed GET is harmless. Specifications and
configuration remain trusted inputs. Legacy server entry points do not implement
this operation policy; use the primary `openapi-mcp` executable.

The earlier `ServerConfig.from_file()` modified `os.environ`, potentially leaving
policy or credentials for a later instance in the same process. File loading now
uses decoded settings sources without mutating the environment. Precedence is
process environment, then `.env`, then file values. Tests cover typed JSON lists,
conflicting settings, independent instances, and the precedence order.

## Shared-fixture comparison

The reproducible fixture is `test/fixtures/adapter-conformance.json`; the harness
is `scripts/compare_openapi_adapters.py`. Both adapters use the same document and
synthetic responses. HTTP MockTransport captures the outgoing requests; TCP
connections are blocked by the harness. The native provider is configured with
`strict_input_validation=True`, exact escaped route maps, and a final EXCLUDE
rule. Its default catch-all behavior is therefore not used to select tools.

JSON/form input fields are translated explicitly between the current nested
`body` argument and the native provider's flattened arguments. This is an observed
migration requirement, not evidence of interchangeable public tool schemas.

| Shared expectation | Current adapter | Native provider |
| --- | --- | --- |
| Inherited path parameter, scalar query, custom header | Pass | Pass |
| JSON body using a local component reference | Pass | Pass |
| `style=form, explode=false` query array encoded as one comma-separated value | Gap: repeated query keys | Pass |
| URL-encoded form body with correct content type | Gap: JSON body | Pass |
| Reject `quantity=0` when the schema says `minimum: 1`, before sending a request | Pass | Gap: request sent |
| Successful request preview with no outgoing request | Pass | Gap: no preview contract |
| Omitted operation rejected without an upstream request | Pass | Pass |
| HTTP 503 represented as an MCP tool error | Pass | Pass |

Both Python 3.12 and 3.10 produced this matrix with FastMCP 4.1.6 / mcp 2.3.0.
Each adapter meets six of these eight deliberately selected expectations. That
is not a general benchmark, security score, or comprehensive conformance test.
The minimum-value observation concerns this generated tool and call path; it is
not a claim that every native tool bypasses all validation. Native dry-run input
is rejected under strict mode and does not supply a successful preview.

The comparison exits **1** when any cell is a gap. The expected behavior was not
weakened to make unsupported features pass. Initial exploratory output included
a harness error (opening an already-open mock client); that run was corrected
and is not used as evidence about either adapter. The accepted reports are
`adapter-comparison-final.json` (Python 3.12) and `adapter-comparison-310.json`.

Reproduce from the repository root after installing the development dependencies:

```bash
python scripts/compare_openapi_adapters.py --output build/adapter-comparison.json
```

The current adapter remains unchanged for unsupported array serialization and
form bodies in this step. Those remain documented limitations, not validated
features. A migration should retain explicit schema validation and preview
handling while replacing request serialization with the native provider.

## Validation

The first policy test run, before implementation, had 18 failures and one pass.
The finished policy suite contains 21 cases. The combined offline suite has:

- **173 passed, 11 explicitly skipped** on Python 3.12.9 and Python 3.10.4.
- The Python 3.12 run also passed with UserWarning promoted to an error. One
  retained deprecated-module import emits a separate DeprecationWarning.
- Black, isort, flake8, and Bandit pass for the checked source. No CI checks were
  disabled. Mypy remains failing: 75 errors versus 76 after the first phase and
  85 in the original source under the same toolchain.
- Remote example specifications were read to verify that the selected Docker
  paths exist (`GET /compact` and `GET /pet/{petId}`). No API operations were
  executed during that check. Docker itself was not built or run.

Evidence and command outputs are retained under ignored
`build/review-20261105/`. The follow-up commands were:

```bash
build/review-20261105/venv/bin/python -m pytest test/ -q -W error::UserWarning
build/review-20261105/venv310/bin/python -m pytest test/ -q
build/review-20261105/venv/bin/python scripts/compare_openapi_adapters.py --output build/review-20261105/adapter-comparison-final.json
build/review-20261105/venv310/bin/python scripts/compare_openapi_adapters.py --output build/review-20261105/adapter-comparison-310.json
build/review-20261105/venv/bin/mypy src/openapi_mcp --ignore-missing-imports
```

Formatting/static checks also included the new policy tests and comparison script.
The initial dependency audit remains applicable: no dependencies changed in this
follow-up. These automated results are not an independent human review.

## Next step

Prototype native request conversion behind the existing input schema, validation,
operation policy, and preview interface. Require the two current request-format
gaps to pass while retaining the six already passing expectations. Extend the
fixtures to multipart data, parameter references, response shapes, and supported
MCP transports before selecting a default adapter. Per-user authentication and
resource limits remain separate work items.

Primary documentation consulted:
[FastMCP OpenAPI integration](https://gofastmcp.com/integrations/openapi).
The reported matrix comes from local execution against the installed source,
not from extrapolating that documentation.
