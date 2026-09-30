import os
import socket
import tempfile
from functools import lru_cache


def setting(name, default=None):
    return os.environ.get(name) or default


@lru_cache(maxsize=None)
def azure_credential():
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


@lru_cache(maxsize=None)
def secret(name):
    value = os.environ.get(name)
    if value:
        return value
    vault_url = os.environ.get("KEY_VAULT_URL")
    if not vault_url:
        return None
    from azure.core.exceptions import ResourceNotFoundError
    from azure.keyvault.secrets import SecretClient

    client = SecretClient(vault_url=vault_url, credential=azure_credential())
    try:
        return client.get_secret(name.lower().replace("_", "-")).value
    except ResourceNotFoundError:
        return None


def data_dir():
    path = setting("DATA_DIR", os.path.join(tempfile.gettempdir(), "cloudnotes"))
    os.makedirs(path, exist_ok=True)
    return path


def instance_name():
    return os.environ.get("WEBSITE_INSTANCE_ID", "")[:12] or socket.gethostname()
