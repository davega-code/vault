# vault

Back up a local folder of photos/files to cloud storage. A lightweight,
standalone companion to
[`lightroom-cli`](https://github.com/davega-code/lightroom-cli): export your
photos to a folder however you like, then `vault push` them to the cloud.

`vault` is a **generic file exporter** — it uploads every file in a folder,
recursively. v1 targets **Azure Blob Storage**; other providers may come later.

## How it works

```
<any folder of files>  ──►  vault push  ──►  Azure Blob container
```

- Uploads are **idempotent**: files already in the container are skipped, so
  re-running a backup only sends what's new (use `--overwrite` to force).
- Files are **streamed** from disk, so large photos and videos don't have to fit
  in memory.
- A failure on one file is reported but **doesn't abort** the rest of the backup.
- **No secrets are stored.** Authentication uses Azure AD via
  `DefaultAzureCredential` (e.g. `az login`); only the account URL and container
  name are saved to `~/.vault/config.json`.

## Prerequisites

1. An Azure Storage account and a **container** (create it ahead of time — v1
   does not create containers).
2. Sign in with an identity that has the **Storage Blob Data Contributor** role
   on the account or container:
   ```bash
   az login
   ```
   (Any `DefaultAzureCredential` source works too: managed identity, a service
   principal via `AZURE_*` env vars, Visual Studio / VS Code sign-in, etc.)

## Install

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync                 # install dependencies
uv run vault --help     # run without installing globally
```

Or install it as a tool so `vault` is on your PATH:

```bash
uv tool install --editable .
```

## Configure a destination

Save your account URL and container once:

```bash
vault config set \
  --account-url https://<account>.blob.core.windows.net \
  --container photos

vault config show
```

Precedence for both values is: command flag > environment variable
(`VAULT_ACCOUNT_URL` / `VAULT_CONTAINER`) > `~/.vault/config.json`.

## Back up a folder

```bash
vault push ./downloads
```

Every file under `./downloads` is uploaded to the container. Each blob is named
by the file's path **relative to the folder** (using `/` separators), so the
folder structure is preserved.

Options:

- `--container, -c TEXT` — target container (overrides config).
- `--prefix, -p TEXT` — prefix prepended to every blob name, e.g.
  `-p 2026/vacation` stores `photo.jpg` as `2026/vacation/photo.jpg`.
- `--account-url TEXT` — account URL (overrides config).
- `--overwrite, -f` — re-upload files that already exist (default: skip them).

Progress is printed per file, followed by an `uploaded / skipped / failed`
summary. If any file failed, the command exits non-zero.

## Using it with lightroom-cli

`vault` is independent from `lightroom-cli`, but they compose naturally — export
first, then back up the folder:

```bash
lightroom-cli albums download <album-id> --dest ./downloads
vault push ./downloads --prefix lightroom
```

## Development

```bash
uv sync          # install dependencies
uv run pytest -q # run the test suite
```

Layout mirrors `lightroom-cli`: source lives under `src/` (imported as top-level
modules via `pythonpath = ["src"]`), tests use injected fakes so no test touches
the network.
