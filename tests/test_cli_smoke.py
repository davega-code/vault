from typer.testing import CliRunner

import cli
import config
from cli import app

runner = CliRunner()


def test_app_shows_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "push" in result.output
    assert "config" in result.output


def test_config_shows_help():
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "set" in result.output
    assert "show" in result.output


def test_config_set_and_show_roundtrip(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "default_config_path", lambda: path)
    result = runner.invoke(
        app,
        [
            "config",
            "set",
            "--account-url",
            "https://acct.blob.core.windows.net",
            "--container",
            "photos",
        ],
    )
    assert result.exit_code == 0, result.output
    shown = runner.invoke(app, ["config", "show"])
    assert "https://acct.blob.core.windows.net" in shown.output
    assert "photos" in shown.output


def test_push_requires_destination(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "default_config_path", lambda: path)
    monkeypatch.delenv("VAULT_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("VAULT_CONTAINER", raising=False)
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"A")
    result = runner.invoke(app, ["push", str(src)])
    assert result.exit_code == 1
    assert "config set" in result.output


def test_push_uploads_via_fake_store(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    config.save_config(
        config.VaultConfig(account_url="https://acct.blob.core.windows.net", container="photos"),
        path,
    )
    monkeypatch.setattr(config, "default_config_path", lambda: path)
    monkeypatch.delenv("VAULT_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("VAULT_CONTAINER", raising=False)

    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.jpg").write_bytes(b"A")
    (src / "sub" / "b.jpg").write_bytes(b"B")

    captured = {}

    class FakeStore:
        def __init__(self):
            self.uploaded = {}

        def verify(self):
            captured["verified"] = True

        def exists(self, name):
            return False

        def upload(self, name, data, *, overwrite):
            self.uploaded[name] = data.read()

    fake = FakeStore()
    monkeypatch.setattr(
        cli.AzureBlobStore, "connect", classmethod(lambda cls, account_url, container: fake)
    )

    result = runner.invoke(app, ["push", str(src)])
    assert result.exit_code == 0, result.output
    assert captured.get("verified") is True
    assert set(fake.uploaded) == {"a.jpg", "sub/b.jpg"}
    assert "2 uploaded" in result.output


def test_push_reports_failures_and_exits_nonzero(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    config.save_config(
        config.VaultConfig(account_url="https://acct.blob.core.windows.net", container="photos"),
        path,
    )
    monkeypatch.setattr(config, "default_config_path", lambda: path)
    monkeypatch.delenv("VAULT_ACCOUNT_URL", raising=False)
    monkeypatch.delenv("VAULT_CONTAINER", raising=False)

    src = tmp_path / "src"
    src.mkdir()
    (src / "a.jpg").write_bytes(b"A")

    from storage import VaultError

    class FailingStore:
        def verify(self):
            pass

        def exists(self, name):
            return False

        def upload(self, name, data, *, overwrite):
            raise VaultError("nope")

    monkeypatch.setattr(
        cli.AzureBlobStore,
        "connect",
        classmethod(lambda cls, account_url, container: FailingStore()),
    )

    result = runner.invoke(app, ["push", str(src)])
    assert result.exit_code == 1
    assert "1 failed" in result.output
