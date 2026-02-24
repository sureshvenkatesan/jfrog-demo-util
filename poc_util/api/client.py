"""Base HTTP client with Bearer auth for Xray/Worker APIs."""

from __future__ import annotations

import requests


class HttpClient:
    """Thin wrapper: session with Bearer token, JSON POST."""

    def __init__(self, base_url: str, token: str, *, verify: bool = True) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.headers["Content-Type"] = "application/json"
        self._session.verify = verify

    def _url(self, path: str) -> str:
        """Full URL for path (relative to base_url). Path must start with /."""
        return self.base_url + path if path.startswith("/") else self.base_url + "/" + path

    def url_for(self, path: str) -> str:
        """Full URL for path (for dry-run display)."""
        return self._url(path)

    def post(self, path: str, json_body: dict) -> requests.Response:
        """POST path (relative to base_url) with JSON body. Path must start with /."""
        return self._session.post(self._url(path), json=json_body, timeout=60)

    def delete(self, path: str) -> requests.Response:
        """DELETE path (relative to base_url). Path must start with /."""
        return self._session.delete(self._url(path), timeout=60)
