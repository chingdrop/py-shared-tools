# py-shared-tools

Small, dependency-minimal utilities reused across personal projects. Meant to
be consumed as a git submodule (added at a path like `vendor/py-shared-tools`
in a consuming repo) plus a `uv` path dependency, rather than copy-pasted
between projects.

Ships a `py.typed` marker (PEP 561), so a consumer's own `mypy`/`pyright` run
checks against this package's real inline type hints instead of treating it
as untyped — no `ignore_missing_imports` override needed for `shared_tools.*`
in a consumer's own config.

## What's here

- `shared_tools/rest_adapter.py` — `RestAdapter`/`RestAdapterConfig`, a thin
  `requests.Session` wrapper with retries, content-type-aware response
  parsing, and a unified request method.
- `shared_tools/retry.py` — `call_with_retry`, a generic, HTTP-agnostic
  retry-with-backoff loop for a call that can fail either by raising an
  exception or by returning a "successful but unusable" result (an HTML error
  page instead of JSON, a response that decodes fine but isn't the shape
  expected). Complements `RestAdapter`'s own transport-level retries (429/5xx
  via urllib3), which have no way to see a problem in a `200`'s body. Used by
  `surface-scan`'s crt.sh client; a good fit for `credential-audit`'s HIBP
  range client too (not yet migrated — see that project's own follow-up).
- `shared_tools/storage.py` — `ObjectStorage`/`StorageError`, a small S3-API
  wrapper (works against AWS S3 or a self-hosted MinIO) built around handing
  out short-lived presigned PUT URLs rather than standing credentials.
  Requires the `storage` extra (`boto3`); everything else in this package
  works without it.
- `shared_tools/config.py` — `resolve_env_refs`/`ConfigError`, the `${VAR}`
  secret-resolution rule shared by every consumer's own `config.yaml` + `.env`
  loader: an unset `${VAR}` resolves to `None` (a valid "no credentials
  configured" state), not an error. Each consumer keeps its own `AppConfig`
  shape and YAML-section parsing; only this one resolution rule is shared.
  Also `StorageConfig`/`parse_storage_config`/`get_storage` — the S3-compatible
  object-storage config shape + builder for `shared_tools/script_export.py`'s
  handoff, byte-for-byte identical in `agent-parity` and `credential-audit`'s
  own `config.py` before this was extracted.
- `shared_tools/config_loader.py` — `ConfigLoader`, a lazy, reloadable
  `MutableMapping` over a JSON or YAML config file, with dot-separated
  nested-key lookup (`config.get("a.b.c")`) and optional `${VAR}`-within-a-
  string expansion via `os.path.expandvars`. Byte-for-byte identical in
  `vega-tools` and `vt-console` before being extracted here. A different
  rule from `shared_tools.config`'s `resolve_env_refs` (see that module's
  docstring) — this one owns the file I/O and parsing itself; pick whichever
  shape a given consumer's config actually needs. YAML support needs the
  `yaml` extra (`pyyaml`); JSON works without it. Includes `.copy()` — a
  shallow, in-memory snapshot that still supports dot-notation `.get()`,
  matching a call site that mutates its own working copy of a shared
  `ctx.obj` (`vega-tools`' `parse_report` CLI group).
- `shared_tools/atomic_io.py` — `atomic_write`/`ensure_dir`, crash-safe local
  file writes (write to a temp file in the same directory, then
  `os.replace` into place, so a reader or a crash mid-write never sees a
  partial file) and idempotent directory creation. Stdlib-only.
- `shared_tools/logging_setup.py` — `setup_logging`, a console-logging setup
  for CLI scripts that's idempotent by construction: calling it again on the
  same logger updates the level but never attaches a second handler, so a
  script and something it imports (or a test re-running the same entrypoint)
  can both call it without doubled-up log lines. Stdlib-only.
- `shared_tools/remote_exec.py` — `VendorConnector`/`ConnectorError`/
  `ConnectorRegistry`, the generic parts of a vendor security-console
  connector: a credentialed `RestAdapter` session, live-vs-fixture dispatch
  for `deploy_and_run()` (push a script to a managed endpoint, poll until
  done, return its output — SentinelOne Remote Script Orchestration, Carbon
  Black Live Response, ...), and a per-project vendor registry. What "fixture
  mode" actually returns, and anything domain-specific (e.g. fetching an
  inventory), is left to each consumer's own subclass — this only owns the
  mechanics every vendor connector needs regardless of what it fetches.
- `shared_tools/sentinelone.py` — `SentinelOneRSOMixin`, the actual SentinelOne
  Remote Script Orchestration API calls (upload the script, execute it,
  poll `remote-scripts/status`, fetch the result) shared verbatim by
  `agent-parity` and `credential-audit`'s own `SentinelOneConnector` classes.
  A mixin, not a full base class, so each consumer combines it with its own
  project-specific base (`class SentinelOneConnector(SentinelOneRSOMixin,
  AgentConnector)`, etc.) rather than forcing one inheritance shape on
  everyone.
- `shared_tools/script_export.py` — `run_script_export`/`ScriptExecutionError`,
  the storage-backed script-export handoff: push a script via a
  `VendorConnector`, prefer a presigned-upload-URL round trip through
  `ObjectStorage` over trusting the connector's own remote-execution output
  channel (which doesn't reliably preserve a CSV's exact formatting), fall
  back to the connector's direct return value in fixture mode. Parameterized
  by `object_key_prefix`/`header_marker`/`what` — this was
  `agent-parity`'s `run_ad_export` and `credential-audit`'s
  `run_ad_metadata_export`, byte-for-byte identical logic under two names,
  before being extracted here. Each consumer's own `deployment/script_runner.py`
  is now a thin wrapper supplying its own script-path constant and parameters.

## Using this in a consuming project

```console
git submodule add <this-repo-url> vendor/py-shared-tools
uv add --editable vendor/py-shared-tools[storage]   # drop [storage] if you don't need ObjectStorage
```

```python
from shared_tools.rest_adapter import RestAdapter, RestAdapterConfig
from shared_tools.storage import ObjectStorage, StorageError
from shared_tools.config import resolve_env_refs, ConfigError, StorageConfig, get_storage
from shared_tools.config_loader import ConfigLoader
from shared_tools.atomic_io import atomic_write, ensure_dir
from shared_tools.logging_setup import setup_logging
from shared_tools.remote_exec import VendorConnector, ConnectorError, ConnectorRegistry
from shared_tools.sentinelone import SentinelOneRSOMixin
from shared_tools.script_export import run_script_export, ScriptExecutionError
```

To pick up changes made in a consuming project's clone of this submodule (or
made directly here), commit inside `vendor/py-shared-tools`, then in the
consuming repo: `git add vendor/py-shared-tools && git commit` to record the
new pinned commit.

## Testing

```console
uv sync
uv run pytest
```
