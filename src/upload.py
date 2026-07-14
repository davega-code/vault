from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from storage import AzureBlobStore, VaultError

# (index, total, blob_name, status) where status is uploaded | skipped | failed.
ProgressFn = Callable[[int, int, str, str], None]


@dataclass
class UploadResult:
    uploaded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)


def collect_files(folder: Path) -> list[Path]:
    """Every file under ``folder``, recursively, sorted for stable ordering."""
    return sorted(p for p in folder.rglob("*") if p.is_file())


def blob_name(root: Path, path: Path, prefix: str = "") -> str:
    """Blob name = ``prefix`` + ``path`` as a POSIX path relative to ``root``."""
    rel = path.relative_to(root).as_posix()
    prefix = prefix.strip("/")
    return f"{prefix}/{rel}" if prefix else rel


def upload_folder(
    store: AzureBlobStore,
    folder: Path,
    *,
    files: list[Path] | None = None,
    prefix: str = "",
    overwrite: bool = False,
    on_progress: ProgressFn | None = None,
) -> UploadResult:
    """Upload every file under ``folder`` to ``store``.

    Files already present are skipped unless ``overwrite`` is set. Each file is
    streamed from disk rather than read fully into memory. A failure on one file
    is recorded and does not abort the rest of the backup. Pass ``files`` to
    reuse an already-collected listing instead of walking ``folder`` again.
    """
    if files is None:
        files = collect_files(folder)
    result = UploadResult()
    total = len(files)

    for index, path in enumerate(files, start=1):
        name = blob_name(folder, path, prefix)
        try:
            if not overwrite and store.exists(name):
                result.skipped.append(name)
                _report(on_progress, index, total, name, "skipped")
                continue
            with path.open("rb") as fh:
                store.upload(name, fh, overwrite=overwrite)
        except (VaultError, OSError) as exc:
            result.failed.append((name, str(exc)))
            _report(on_progress, index, total, name, "failed")
            continue

        result.uploaded.append(name)
        _report(on_progress, index, total, name, "uploaded")

    return result


def _report(
    on_progress: ProgressFn | None,
    index: int,
    total: int,
    name: str,
    status: str,
) -> None:
    if on_progress is not None:
        on_progress(index, total, name, status)
