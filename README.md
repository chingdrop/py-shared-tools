# py-shared-tools

Small, dependency-minimal utilities reused across personal projects. Meant to
be consumed as a git submodule (added at a path like `vendor/py-shared-tools`
in a consuming repo) plus a `uv` path dependency, rather than copy-pasted
between projects.

## What's here

- `shared_tools/rest_adapter.py` — `RestAdapter`/`RestAdapterConfig`, a thin
  `requests.Session` wrapper with retries, content-type-aware response
  parsing, and a unified request method.
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

## Using this in a consuming project

```console
git submodule add <this-repo-url> vendor/py-shared-tools
uv add --editable vendor/py-shared-tools[storage]   # drop [storage] if you don't need ObjectStorage
```

```python
from shared_tools.rest_adapter import RestAdapter, RestAdapterConfig
from shared_tools.storage import ObjectStorage, StorageError
from shared_tools.config import resolve_env_refs, ConfigError
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
