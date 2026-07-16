"""JSON/YAML configuration file loader with dict-like access.

Byte-for-byte identical between ``vega-tools`` and ``vt-console`` before this
was extracted: a lazy, reloadable ``MutableMapping`` over a JSON or YAML
file, with dot-separated nested-key lookup and optional environment-variable
expansion.

Distinct from ``shared_tools.config``'s ``resolve_env_refs``: that module
expects a config already parsed into a dict and only resolves whole-string
``${VAR}`` references (an unset variable resolves to ``None``, never an
error). This module owns the file I/O and parsing itself, and its
``env_expand`` uses ``os.path.expandvars``/``expanduser`` substitution
*within* a larger string (e.g. ``"${HOME}/data"``) instead, leaving an unset
variable as the literal ``$VAR`` text rather than turning it into ``None``.
Two different rules for two different shapes of config — pick whichever a
given consumer's own config actually needs.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any, Iterator

from shared_tools.config import ConfigError


class ConfigLoader(MutableMapping):
    """Read-only, reloadable dict-like view over a JSON or YAML config file.

    YAML support imports PyYAML lazily, only when loading a ``.yaml``/
    ``.yml`` file — a JSON-only consumer never needs it installed (add the
    ``yaml`` extra when it does).
    """

    def __init__(
            self,
            filepath: Path | str,
            *,
            env_expand: bool = False,
            logger: logging.Logger | None = None,
    ) -> None:
        self.filepath = Path(filepath)
        self.env_expand = env_expand
        self.logger = logger or logging.getLogger(__name__)
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """Reload the configuration file into memory.

        Raises ``ConfigError`` if the file is missing, malformed, or its
        root isn't a JSON/YAML object.
        """
        if not self.filepath.exists():
            raise ConfigError(f"Configuration file not found: {self.filepath}")
        text = self.filepath.read_text(encoding="utf-8")
        suffix = self.filepath.suffix.lower()
        try:
            if suffix in (".yaml", ".yml"):
                import yaml
                data = yaml.safe_load(text)
            elif suffix == ".json":
                data = json.loads(text)
            else:
                raise ConfigError(f"Unsupported config file extension: {suffix!r}")
            if not isinstance(data, dict):
                raise ConfigError("Configuration root must be a JSON/YAML object")
        except json.JSONDecodeError as exc:
            raise ConfigError(f"JSON syntax error in {self.filepath}: {exc}") from exc
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f"Error loading config: {exc}") from exc

        self._data = data
        self.logger.debug("Loaded config from %s", self.filepath)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value by key, supporting dot notation for nested dicts.

        Expands environment variables (and ``~``) if ``env_expand=True`` and
        the resolved value is a string.
        """
        current: Any = self._data
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        if self.env_expand and isinstance(current, str):
            return os.path.expanduser(os.path.expandvars(current))
        return current

    # -- MutableMapping -------------------------------------------------------

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        raise TypeError("ConfigLoader is read-only")

    def __delitem__(self, key: str) -> None:
        raise TypeError("ConfigLoader is read-only")

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def copy(self) -> "ConfigLoader":
        """Return a shallow, in-memory copy that still supports dot-notation
        ``.get()``.

        ``MutableMapping`` doesn't provide ``.copy()``, and a plain
        ``dict(loader)`` would silently drop dot-notation lookups — a caller
        that wants to hand a mutable-looking snapshot to something else
        (e.g. a Click command mutating its own working copy of a shared
        ``ctx.obj``) needs an actual ``ConfigLoader`` back. Doesn't re-read
        ``filepath`` from disk.
        """
        new = ConfigLoader.__new__(ConfigLoader)
        new.filepath = self.filepath
        new.env_expand = self.env_expand
        new.logger = self.logger
        new._data = dict(self._data)
        return new
