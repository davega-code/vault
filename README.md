# vault

Back up a local folder of photos/files to cloud storage. A lightweight,
standalone companion to [`lightroom-cli`](https://github.com/davega-code/lightroom-cli):
export your photos to a folder however you like, then `vault push` them to the
cloud. v1 targets **Azure Blob Storage**.

> Status: initial scaffold. See [the spec](../specs/vault/spec.md) for the full plan.

## Development

This project uses [uv](https://docs.astral.sh/uv/).

```bash
uv sync          # install dependencies
uv run pytest -q # run the test suite
```
