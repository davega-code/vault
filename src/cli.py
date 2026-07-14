import os
import sys
from pathlib import Path

import typer

import config
import upload
from storage import AzureBlobStore, VaultError


def _ensure_utf8_output() -> None:
    """Render Unicode file names correctly on consoles whose default encoding
    isn't UTF-8 — notably cp1252 on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


_ensure_utf8_output()

app = typer.Typer(
    help="Back up a local folder of photos/files to cloud storage (Azure Blob Storage).",
    no_args_is_help=True,
)
config_app = typer.Typer(help="Manage the backup destination.", no_args_is_help=True)
app.add_typer(config_app, name="config")


@config_app.command("set")
def config_set(
    account_url: str = typer.Option(
        None,
        "--account-url",
        help="Azure Blob account URL, e.g. https://<account>.blob.core.windows.net",
    ),
    container: str = typer.Option(None, "--container", "-c", help="Target container name."),
) -> None:
    """Save (non-secret) destination settings to ~/.vault/config.json."""
    cfg = config.load_config()
    if account_url is not None:
        cfg.account_url = account_url
    if container is not None:
        cfg.container = container
    config.save_config(cfg)
    typer.secho("Saved destination settings.", fg=typer.colors.GREEN)
    typer.echo(f"  account_url: {cfg.account_url or '(unset)'}")
    typer.echo(f"  container:   {cfg.container or '(unset)'}")
    typer.echo(f"Config: {config.default_config_path()}")


@config_app.command("show")
def config_show() -> None:
    """Show the current destination settings."""
    cfg = config.load_config()
    typer.echo(f"account_url: {cfg.account_url or '(unset)'}")
    typer.echo(f"container:   {cfg.container or '(unset)'}")
    typer.echo(f"config:      {config.default_config_path()}")


def _require_destination(account_url: str | None, container: str | None) -> tuple[str, str]:
    """Return (account_url, container) or exit with an actionable message."""
    missing = []
    if not account_url:
        missing.append("account URL")
    if not container:
        missing.append("container")
    if missing:
        typer.secho(
            f"No {' and '.join(missing)} configured. Set a destination with:\n"
            "  vault config set --account-url https://<account>.blob.core.windows.net "
            "--container <name>\n"
            "or pass --account-url / --container, or set the VAULT_ACCOUNT_URL / "
            "VAULT_CONTAINER environment variables.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    return account_url, container  # type: ignore[return-value]


@app.command("push")
def push(
    folder: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Local folder to back up (uploaded recursively).",
    ),
    container: str = typer.Option(
        None, "--container", "-c", help="Target container (overrides config)."
    ),
    prefix: str = typer.Option(
        "", "--prefix", "-p", help="Prefix prepended to every blob name."
    ),
    account_url: str = typer.Option(
        None, "--account-url", help="Azure Blob account URL (overrides config)."
    ),
    overwrite: bool = typer.Option(
        False, "--overwrite", "-f", help="Re-upload files that already exist."
    ),
) -> None:
    """Upload every file in FOLDER to the configured Azure Blob container."""
    cfg = config.load_config()
    resolved_account = config.resolve_account_url(account_url, os.environ, cfg)
    resolved_container = config.resolve_container(container, os.environ, cfg)
    account, container_name = _require_destination(resolved_account, resolved_container)

    files = upload.collect_files(folder)
    if not files:
        typer.echo(f"No files found under {folder}. Nothing to back up.")
        return

    def on_progress(index: int, total: int, name: str, status: str) -> None:
        typer.echo(f"[{index}/{total}] {status:<9} {name}")

    try:
        store = AzureBlobStore.connect(account, container_name)
        store.verify()
        typer.echo(
            f"Backing up {len(files)} file(s) from {folder} to container "
            f"'{container_name}'..."
        )
        result = upload.upload_folder(
            store,
            folder,
            files=files,
            prefix=prefix,
            overwrite=overwrite,
            on_progress=on_progress,
        )
    except VaultError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(
        f"Done. {len(result.uploaded)} uploaded, "
        f"{len(result.skipped)} skipped, {len(result.failed)} failed.",
        fg=typer.colors.GREEN,
    )
    for name, reason in result.failed:
        typer.secho(f"  failed: {name} — {reason}", fg=typer.colors.YELLOW, err=True)
    if result.failed:
        raise typer.Exit(code=1)
