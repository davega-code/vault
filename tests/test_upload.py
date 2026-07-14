import upload
from storage import VaultError


class FakeStore:
    """Stands in for AzureBlobStore; tracks existing names and captures uploads."""

    def __init__(self, existing=(), fail_on=None):
        self._existing = set(existing)
        self._fail_on = dict(fail_on or {})
        self.uploaded = {}  # name -> bytes
        self.overwrites = {}  # name -> overwrite flag

    def exists(self, name):
        return name in self._existing

    def upload(self, name, data, *, overwrite):
        if name in self._fail_on:
            raise self._fail_on[name]
        self.uploaded[name] = data.read()
        self.overwrites[name] = overwrite


def _make_tree(root, files):
    for rel, content in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def test_uploads_all_files_with_relative_posix_names(tmp_path):
    _make_tree(tmp_path, {"a.jpg": b"A", "sub/b.jpg": b"B", "sub/deep/c.jpg": b"C"})
    store = FakeStore()
    result = upload.upload_folder(store, tmp_path)
    assert store.uploaded == {"a.jpg": b"A", "sub/b.jpg": b"B", "sub/deep/c.jpg": b"C"}
    assert sorted(result.uploaded) == ["a.jpg", "sub/b.jpg", "sub/deep/c.jpg"]
    assert result.skipped == []
    assert result.failed == []


def test_applies_prefix(tmp_path):
    _make_tree(tmp_path, {"a.jpg": b"A", "sub/b.jpg": b"B"})
    store = FakeStore()
    upload.upload_folder(store, tmp_path, prefix="/backup/2026/")
    assert set(store.uploaded) == {"backup/2026/a.jpg", "backup/2026/sub/b.jpg"}


def test_skips_existing_by_default(tmp_path):
    _make_tree(tmp_path, {"a.jpg": b"A", "b.jpg": b"B"})
    store = FakeStore(existing=["a.jpg"])
    result = upload.upload_folder(store, tmp_path)
    assert result.skipped == ["a.jpg"]
    assert result.uploaded == ["b.jpg"]
    assert "a.jpg" not in store.uploaded


def test_overwrite_reuploads_existing(tmp_path):
    _make_tree(tmp_path, {"a.jpg": b"NEW"})
    store = FakeStore(existing=["a.jpg"])
    result = upload.upload_folder(store, tmp_path, overwrite=True)
    assert result.uploaded == ["a.jpg"]
    assert store.uploaded["a.jpg"] == b"NEW"
    assert store.overwrites["a.jpg"] is True


def test_records_per_file_failure_and_continues(tmp_path):
    _make_tree(tmp_path, {"a.jpg": b"A", "b.jpg": b"B"})
    store = FakeStore(fail_on={"a.jpg": VaultError("boom")})
    result = upload.upload_folder(store, tmp_path)
    assert result.uploaded == ["b.jpg"]
    assert len(result.failed) == 1
    assert result.failed[0][0] == "a.jpg"


def test_reports_progress(tmp_path):
    _make_tree(tmp_path, {"a.jpg": b"A"})
    events = []
    upload.upload_folder(
        store=FakeStore(),
        folder=tmp_path,
        on_progress=lambda i, t, n, s: events.append((i, t, n, s)),
    )
    assert events == [(1, 1, "a.jpg", "uploaded")]


def test_empty_folder_yields_empty_result(tmp_path):
    result = upload.upload_folder(FakeStore(), tmp_path)
    assert result.uploaded == []
    assert result.skipped == []
    assert result.failed == []
