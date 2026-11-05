# Release candidate 2.0.0rc1 — 2026-11-05

Roger accepted the recommendation to prepare and publish a 2.0 release candidate.
The new major version reflects operation allowlists, HTTP endpoint changes, and
changed tool input schemas. The previous 1.0.4 package is not overwritten.

## Changes required for the candidate

Selected operations using known unsupported request encodings now stop startup
before any tool registration. This includes non-JSON bodies, non-scalar path/query/
header parameters, cookie parameters, parameter references/content, and nondefault
serialization styles. Omitted unsupported operations can coexist with supported
selected routes. Explicit null JSON bodies and structured non-body values are
rejected before authentication. Seventeen new regression cases failed before
these checks and passed afterwards.

The comparison harness still reports the unsupported CSV-array and form-body
expectations as gaps, now with no request sent. It selects each operation in
isolation and records startup rejection rather than crashing on the first
unsupported route. Historical comparison reports remain unchanged. The two
native-provider gaps (minimum validation and successful previews) remain.

The installed-wheel smoke test starts the real console command and talks to it
through both stdio and loopback HTTP using the current FastMCP client. An actual
local upstream server records requests. The test verifies tool discovery,
request previews without credentials or execution, rejected invalid/denied
calls, allowed scalar/JSON calls with synthetic credentials, schema resources,
and HTTP Host/Origin rejection. Four permitted upstream requests are made in
total. No public API is called.

## Validation and release controls

- Python 3.12.9 and 3.10.4: **190 passed, 11 legacy live examples skipped**.
- The Python 3.12 warnings-as-errors check also passed apart from the separately
  recorded deprecated-module import warning.
- Source formatting, lint, and Bandit checks passed. Existing mypy debt remains;
  it is not a passed release gate.
- A clean virtual environment installed the built 2.0.0rc1 wheel, not the editable
  source. Both real transport tests passed. Metadata and package versions agree.
- CI now runs the installed-wheel smoke test. The publication workflow runs
  offline regressions, builds the distributions, validates metadata with Twine,
  and tests the wheel in a clean environment before uploading those distributions.
- The release event's tag must match the package version. PyPI authentication uses
  Trusted Publishing for `gujord/OpenAPI-MCP`, workflow `publish.yml`, without an
  environment name. Roger confirmed registering that publisher on PyPI.

Local evidence is retained under ignored `build/release-2.0.0rc1/` and the earlier
`build/review-20261105/` directory. Relevant commands:

```bash
python -m pytest test/ -q
python -m build --outdir build/release-2.0.0rc1/dist
uv venv --python 3.12 build/release-2.0.0rc1/clean-venv
uv pip install --python build/release-2.0.0rc1/clean-venv/bin/python build/release-2.0.0rc1/dist/openapi_mcp_proxy-2.0.0rc1-py3-none-any.whl
build/release-2.0.0rc1/clean-venv/bin/python scripts/smoke_release.py --output build/release-2.0.0rc1/smoke.json
```

[The upgrade guide](../UPGRADING-2.md) describes the compatibility changes and
supported subset. This candidate does not establish full OpenAPI conformance,
per-user MCP authorization, Docker validation, or independent human security
review. The GitHub release and publication run are the authoritative delivery
status; this note records preparation and checks rather than asserting upload
success before it happens.
