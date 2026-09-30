import logging
import mimetypes
import os

from config import azure_credential, secret, setting
from notes import DependencyError

logger = logging.getLogger("cloudnotes")


def storage_client(kind):
    connection_string = secret("STORAGE_CONNECTION_STRING")
    account_name = setting("STORAGE_ACCOUNT_NAME")
    if kind == "blob":
        from azure.storage.blob import BlobServiceClient as Client
    else:
        from azure.storage.queue import QueueServiceClient as Client
    if connection_string:
        return Client.from_connection_string(connection_string)
    if account_name:
        return Client(f"https://{account_name}.{kind}.core.windows.net", credential=azure_credential())
    return None


class LocalFileStore:
    kind = "local"

    def __init__(self, data_dir, container):
        self.container = container
        self.root = os.path.join(data_dir, container)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, name):
        return os.path.join(self.root, os.path.basename(name))

    def save(self, name, data, content_type=None):
        with open(self._path(name), "wb") as file:
            file.write(data)

    def load(self, name):
        path = self._path(name)
        if not os.path.exists(path):
            return None, None
        with open(path, "rb") as file:
            return file.read(), mimetypes.guess_type(name)[0]

    def delete(self, name):
        if os.path.exists(self._path(name)):
            os.remove(self._path(name))

    def names(self):
        return set(os.listdir(self.root))

    def check(self):
        os.listdir(self.root)


class BlobFileStore:
    kind = "blob"

    def __init__(self, service, container):
        from azure.core.exceptions import AzureError, ResourceExistsError, ResourceNotFoundError

        self.container = container
        self._client = service.get_container_client(container)
        self._errors = AzureError
        self._not_found = ResourceNotFoundError
        try:
            self._client.create_container()
        except ResourceExistsError:
            pass
        except AzureError as error:
            logger.warning("cannot create container %s: %s", container, error)

    def _call(self, operation):
        try:
            return operation()
        except self._not_found:
            raise
        except self._errors as error:
            raise DependencyError("storage", error) from error

    def save(self, name, data, content_type=None):
        from azure.storage.blob import ContentSettings

        settings = ContentSettings(content_type=content_type or mimetypes.guess_type(name)[0])
        self._call(lambda: self._client.upload_blob(name, data, overwrite=True, content_settings=settings))

    def load(self, name):
        try:
            blob = self._call(lambda: self._client.download_blob(name))
            return blob.readall(), blob.properties.content_settings.content_type
        except self._not_found:
            return None, None

    def delete(self, name):
        try:
            self._call(lambda: self._client.delete_blob(name))
        except self._not_found:
            pass

    def names(self):
        return self._call(lambda: {blob.name for blob in self._client.list_blobs()})

    def check(self):
        self._call(self._client.get_container_properties)


def create_file_store(container, data_dir):
    service = storage_client("blob")
    if service is None:
        return LocalFileStore(data_dir, container)
    return BlobFileStore(service, container)
