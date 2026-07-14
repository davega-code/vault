from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from azure.storage.blob import ContainerClient


class VaultError(Exception):
    """A backup destination operation failed, with an actionable message."""


@dataclass
class AzureBlobStore:
    """Thin wrapper over an Azure Blob container: existence checks and uploads.

    The underlying ``ContainerClient`` is injected so the store can be faked in
    tests. Use :meth:`connect` to build one authenticated with Azure AD.
    """

    container: "ContainerClient"

    @classmethod
    def connect(cls, account_url: str, container: str) -> "AzureBlobStore":
        """Build a store authenticated via ``DefaultAzureCredential`` (e.g. ``az login``)."""
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        service = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
        return cls(container=service.get_container_client(container))

    def verify(self) -> None:
        """Confirm the container is reachable with the current credentials.

        Surfaces the common misconfigurations (not signed in, missing container,
        no access) up front with an actionable message, before a bulk upload.
        """
        try:
            next(iter(self.container.list_blobs(results_per_page=1)), None)
        except Exception as exc:  # remapped to a VaultError with guidance
            raise _map_error(exc, self._container_name()) from exc

    def exists(self, name: str) -> bool:
        try:
            return self.container.get_blob_client(name).exists()
        except Exception as exc:
            raise _map_error(exc, self._container_name()) from exc

    def upload(self, name: str, data: BinaryIO, *, overwrite: bool) -> None:
        try:
            self.container.upload_blob(name=name, data=data, overwrite=overwrite)
        except Exception as exc:
            raise _map_error(exc, self._container_name()) from exc

    def _container_name(self) -> str:
        return getattr(self.container, "container_name", "the target container")


def _map_error(exc: Exception, container: str) -> VaultError:
    """Translate an Azure SDK exception into an actionable :class:`VaultError`."""
    from azure.core.exceptions import (
        ClientAuthenticationError,
        HttpResponseError,
        ResourceNotFoundError,
    )

    if isinstance(exc, VaultError):
        return exc
    if isinstance(exc, ClientAuthenticationError):
        return VaultError(
            "Could not authenticate to Azure. Sign in with 'az login' (or "
            "configure a managed identity / service principal), then try again. "
            f"Details: {exc}"
        )
    if isinstance(exc, ResourceNotFoundError):
        return VaultError(
            f"Container '{container}' was not found on the storage account. "
            "Create it (e.g. 'az storage container create --name "
            f"{container} --account-name <acct> --auth-mode login') or check the "
            "account URL and container name."
        )
    status = getattr(exc, "status_code", None)
    if isinstance(exc, HttpResponseError) and status == 403:
        return VaultError(
            "Access denied (403). The signed-in identity needs the 'Storage Blob "
            f"Data Contributor' role on the storage account or container "
            f"'{container}'. Assign it and try again."
        )
    if isinstance(exc, HttpResponseError):
        return VaultError(f"Azure Blob request failed ({status}): {exc}")
    return VaultError(f"Unexpected error talking to Azure Blob Storage: {exc}")
