"""Artifactory REST API helpers."""

from __future__ import annotations

from poc_util.api.client import HttpClient


def delete_repository(client: HttpClient, repo_key: str):
    """Delete an Artifactory repository by key. Uses DELETE /artifactory/api/repositories/<repoKey>."""
    path = f"/artifactory/api/repositories/{repo_key}"
    return client.delete(path)
