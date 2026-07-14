from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

ENV_ACCOUNT_URL = "VAULT_ACCOUNT_URL"
ENV_CONTAINER = "VAULT_CONTAINER"


@dataclass
class VaultConfig:
    """Destination settings for backups.

    Only non-secret values are ever stored. Authentication is handled at runtime
    by Azure AD (``DefaultAzureCredential``), so no keys or tokens live here.
    """

    account_url: str | None
    container: str | None


def _defaults() -> VaultConfig:
    return VaultConfig(account_url=None, container=None)


def default_config_path() -> Path:
    return Path.home() / ".vault" / "config.json"


def load_config(path: Path | None = None) -> VaultConfig:
    path = path or default_config_path()
    if not path.exists():
        return _defaults()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Config file at {path} is not valid JSON: {exc}. "
            f"Fix or delete it and try again."
        ) from exc
    base = asdict(_defaults())
    base.update({k: v for k, v in data.items() if k in base})
    return VaultConfig(**base)


def save_config(cfg: VaultConfig, path: Path | None = None) -> None:
    path = path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")


def resolve_account_url(flag: str | None, env: Mapping[str, str], cfg: VaultConfig) -> str | None:
    return flag or env.get(ENV_ACCOUNT_URL) or cfg.account_url


def resolve_container(flag: str | None, env: Mapping[str, str], cfg: VaultConfig) -> str | None:
    return flag or env.get(ENV_CONTAINER) or cfg.container
