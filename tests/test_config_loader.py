"""ConfigLoader tests: JSON/YAML parsing, dot-notation lookup, reload,
env-expansion, and the read-only MutableMapping contract.
"""

import pytest

from shared_tools.config import ConfigError
from shared_tools.config_loader import ConfigLoader


def test_loads_json_file(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"a": {"b": "value"}}')
    config = ConfigLoader(path)
    assert config.get("a.b") == "value"


def test_loads_yaml_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("a:\n  b: value\n")
    config = ConfigLoader(path)
    assert config.get("a.b") == "value"


def test_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        ConfigLoader(tmp_path / "missing.json")


def test_malformed_json_raises_config_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json")
    with pytest.raises(ConfigError, match="syntax error"):
        ConfigLoader(path)


def test_unsupported_extension_raises_config_error(tmp_path):
    path = tmp_path / "config.txt"
    path.write_text("irrelevant")
    with pytest.raises(ConfigError, match="Unsupported config file extension"):
        ConfigLoader(path)


def test_non_object_root_raises_config_error(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[1, 2, 3]")
    with pytest.raises(ConfigError, match="must be a JSON/YAML object"):
        ConfigLoader(path)


def test_get_missing_key_returns_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{}")
    config = ConfigLoader(path)
    assert config.get("missing.key") is None
    assert config.get("missing.key", "fallback") == "fallback"


def test_get_partial_path_through_non_dict_returns_default(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"a": "scalar"}')
    config = ConfigLoader(path)
    assert config.get("a.b", "fallback") == "fallback"


def test_env_expand_substitutes_within_string(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_CONFIG_VAR", "resolved")
    path = tmp_path / "config.json"
    path.write_text('{"a": "prefix-${TEST_CONFIG_VAR}-suffix"}')
    config = ConfigLoader(path, env_expand=True)
    assert config.get("a") == "prefix-resolved-suffix"


def test_env_expand_disabled_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_CONFIG_VAR", "resolved")
    path = tmp_path / "config.json"
    path.write_text('{"a": "${TEST_CONFIG_VAR}"}')
    config = ConfigLoader(path)
    assert config.get("a") == "${TEST_CONFIG_VAR}"


def test_reload_picks_up_file_changes(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"a": "first"}')
    config = ConfigLoader(path)
    assert config.get("a") == "first"

    path.write_text('{"a": "second"}')
    config.reload()
    assert config.get("a") == "second"


def test_copy_returns_independent_config_loader(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"a": 1, "b": 2}')
    config = ConfigLoader(path)

    copied = config.copy()
    assert copied is not config
    assert isinstance(copied, ConfigLoader)
    assert dict(copied) == {"a": 1, "b": 2}


def test_copy_preserves_dot_notation_get(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"a": {"b": "value"}}')
    config = ConfigLoader(path)

    copied = config.copy()
    assert copied.get("a.b") == "value"


def test_copy_mutation_does_not_affect_original(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"a": 1}')
    config = ConfigLoader(path)

    copied = config.copy()
    copied._data["a"] = 2
    assert config["a"] == 1


def test_mapping_interface_is_read_only(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"a": 1}')
    config = ConfigLoader(path)

    assert config["a"] == 1
    assert list(config) == ["a"]
    assert len(config) == 1
    with pytest.raises(TypeError):
        config["a"] = 2
    with pytest.raises(TypeError):
        del config["a"]
