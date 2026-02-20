"""Xray API: webhooks, policies, watches."""

from __future__ import annotations

from poc_util.api.client import HttpClient


def post_webhook(client: HttpClient, body: dict) -> object:
    """POST /xray/api/v1/webhooks."""
    return client.post("/xray/api/v1/webhooks", body)


def delete_webhook(client: HttpClient, name: str) -> object:
    """DELETE /xray/api/v1/webhooks/{name}."""
    return client.delete(f"/xray/api/v1/webhooks/{name}")


def post_policy(client: HttpClient, body: dict) -> object:
    """POST /xray/api/v1/policies."""
    return client.post("/xray/api/v1/policies", body)


def delete_policy(client: HttpClient, name: str) -> object:
    """DELETE /xray/api/v1/policies/{name}."""
    return client.delete(f"/xray/api/v1/policies/{name}")


def post_watch(client: HttpClient, body: dict) -> object:
    """POST /xray/api/v2/watches."""
    return client.post("/xray/api/v2/watches", body)


def delete_watch(client: HttpClient, name: str) -> object:
    """DELETE /xray/api/v2/watches/{name}."""
    return client.delete(f"/xray/api/v2/watches/{name}")
