__all__ = [
    "get_httpx_client",
    "BOTO3_CLIENTS",
]

from ._httpx import get_httpx_client
from .aws import BOTO3_CLIENTS
