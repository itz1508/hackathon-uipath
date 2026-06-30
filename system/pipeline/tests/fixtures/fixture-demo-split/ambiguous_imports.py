"""Module importing from an internal generated client."""

from generated_client import ApiClient
from internal_service_sdk import ServiceConnector

def connect():
    client = ApiClient()
    return ServiceConnector(client)