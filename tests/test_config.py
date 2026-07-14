import json

import pytest

import config


def test_load_missing_returns_defaults(tmp_path):
    cfg = config.load_config(tmp_path / "nope.json")
    assert cfg.account_url is None
    assert cfg.container is None


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    cfg = config.VaultConfig(
        account_url="https://acct.blob.core.windows.net",
        container="photos",
    )
    config.save_config(cfg, path)
    loaded = config.load_config(path)
    assert loaded == cfg
    json.loads(path.read_text())


def test_save_never_writes_secret_fields(tmp_path):
    path = tmp_path / "config.json"
    config.save_config(
        config.VaultConfig(account_url="https://a.blob.core.windows.net", container="c"),
        path,
    )
    data = json.loads(path.read_text())
    assert set(data.keys()) == {"account_url", "container"}


def test_resolve_account_url_precedence():
    cfg = config.VaultConfig(account_url="from_file", container=None)
    env = {config.ENV_ACCOUNT_URL: "from_env"}
    assert config.resolve_account_url("from_flag", env, cfg) == "from_flag"
    assert config.resolve_account_url(None, env, cfg) == "from_env"
    assert config.resolve_account_url(None, {}, cfg) == "from_file"
    empty = config.VaultConfig(account_url=None, container=None)
    assert config.resolve_account_url(None, {}, empty) is None


def test_resolve_container_precedence():
    cfg = config.VaultConfig(account_url=None, container="from_file")
    env = {config.ENV_CONTAINER: "from_env"}
    assert config.resolve_container("from_flag", env, cfg) == "from_flag"
    assert config.resolve_container(None, env, cfg) == "from_env"
    assert config.resolve_container(None, {}, cfg) == "from_file"


def test_load_config_corrupt_json_raises(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError):
        config.load_config(path)
