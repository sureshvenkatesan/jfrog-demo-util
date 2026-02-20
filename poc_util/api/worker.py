"""Worker API."""

from __future__ import annotations

from poc_util.api.client import HttpClient


def post_worker(client: HttpClient, body: dict) -> object:
    """POST /worker/api/v1/workers."""
    return client.post("/worker/api/v1/workers", body)


def delete_worker(client: HttpClient, key: str) -> object:
    """DELETE /worker/api/v1/workers/{key}."""
    return client.delete(f"/worker/api/v1/workers/{key}")
