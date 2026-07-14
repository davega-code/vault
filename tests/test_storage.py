import io

import pytest
from azure.core.exceptions import (
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
)

from storage import AzureBlobStore, VaultError


class FakeBlobClient:
    def __init__(self, exists_value=False):
        self._exists_value = exists_value

    def exists(self):
        return self._exists_value


class FakeContainerClient:
    """Stands in for azure.storage.blob.ContainerClient."""

    def __init__(self, container_name="photos", exists_value=False):
        self.container_name = container_name
        self.list_exc = None
        self.list_items = []
        self.blob = FakeBlobClient(exists_value)
        self.last_blob_name = None
        self.uploaded = []
        self.upload_exc = None

    def list_blobs(self, results_per_page=None):
        if self.list_exc:
            raise self.list_exc
        return iter(self.list_items)

    def get_blob_client(self, name):
        self.last_blob_name = name
        return self.blob

    def upload_blob(self, name=None, data=None, overwrite=None):
        if self.upload_exc:
            raise self.upload_exc
        content = data.read() if hasattr(data, "read") else data
        self.uploaded.append((name, content, overwrite))


def _http_error(status):
    err = HttpResponseError("boom")
    err.status_code = status
    return err


def test_verify_ok_when_listing_works():
    AzureBlobStore(FakeContainerClient()).verify()


def test_verify_maps_auth_error():
    c = FakeContainerClient()
    c.list_exc = ClientAuthenticationError("no credentials")
    with pytest.raises(VaultError, match="az login"):
        AzureBlobStore(c).verify()


def test_verify_maps_missing_container():
    c = FakeContainerClient(container_name="mine")
    c.list_exc = ResourceNotFoundError("404")
    with pytest.raises(VaultError, match="mine"):
        AzureBlobStore(c).verify()


def test_verify_maps_permission_denied():
    c = FakeContainerClient()
    c.list_exc = _http_error(403)
    with pytest.raises(VaultError, match="Storage Blob Data Contributor"):
        AzureBlobStore(c).verify()


def test_exists_delegates_to_blob_client():
    c = FakeContainerClient(exists_value=True)
    store = AzureBlobStore(c)
    assert store.exists("a/b.jpg") is True
    assert c.last_blob_name == "a/b.jpg"


def test_upload_streams_and_passes_overwrite():
    c = FakeContainerClient()
    AzureBlobStore(c).upload("x.jpg", io.BytesIO(b"DATA"), overwrite=True)
    assert c.uploaded == [("x.jpg", b"DATA", True)]


def test_upload_maps_generic_http_error():
    c = FakeContainerClient()
    c.upload_exc = _http_error(500)
    with pytest.raises(VaultError, match="500"):
        AzureBlobStore(c).upload("x", io.BytesIO(b"D"), overwrite=False)
