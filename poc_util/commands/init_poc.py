"""Init POC: create Worker, Webhook, Policy, Watch via Python HTTP. Cleanup: delete them."""

from __future__ import annotations

import time
from pathlib import Path

from poc_util.api.client import HttpClient
from poc_util.api.xray import (
    delete_policy,
    delete_watch,
    delete_webhook,
    post_policy,
    post_watch,
    post_webhook,
)
from poc_util.api.worker import delete_worker, post_worker
from poc_util.config import get_jfrog_token, load_config
from poc_util.templates import load_and_parse_resource

INIT_ORDER = ["worker", "webhook", "policy", "watch"]
# Reverse order for cleanup (watch -> policy -> webhook -> worker)
CLEANUP_ORDER = list(reversed(INIT_ORDER))


def _resources_dir(resources_dir: str | Path | None) -> Path:
    if resources_dir is not None:
        return Path(resources_dir)
    candidate = Path(__file__).resolve().parent.parent.parent / "resources"
    return candidate if candidate.is_dir() else Path.cwd() / "resources"


def run_init(
    config_path: str | Path | None = None,
    resources_dir: str | Path | None = None,
    *,
    _client: HttpClient | None = None,
    webhook_delay_seconds: float = 2.0,
    dry_run: bool = False,
) -> int:
    """Load config and resources, POST each entity in order. Returns 0 on success, 1 on failure.

    After creating the webhook, waits webhook_delay_seconds so Xray can register it
    before creating a policy that references it (avoids "unrecognized webhook" errors).
    If dry_run is True, prints the HTTP method and URL (and body for POST) without sending.
    """
    config = load_config(config_path)
    base_url = config["jfrog"]["base_url"].rstrip("/")
    token = get_jfrog_token(config)
    res_dir = _resources_dir(resources_dir)
    client = _client or HttpClient(base_url, token)

    for name in INIT_ORDER:
        url, body = load_and_parse_resource(res_dir, name, config)
        if dry_run:
            print(f"POST {url}")
            continue
        try:
            if name == "worker":
                r = post_worker(client, body)
            elif name == "webhook":
                r = post_webhook(client, body)
            elif name == "policy":
                r = post_policy(client, body)
            elif name == "watch":
                r = post_watch(client, body)
            else:
                continue
            status = r.status_code if hasattr(r, "status_code") else getattr(r, "status", 0)
            if status >= 200 and status < 300:
                print(f"Created {name}: {status}")
                if name == "webhook" and webhook_delay_seconds > 0:
                    time.sleep(webhook_delay_seconds)
            else:
                print(f"Failed {name}: {status} {getattr(r, 'text', getattr(r, 'content', ''))}")
                return 1
        except Exception as e:
            print(f"Error creating {name}: {e}")
            return 1
    return 0


def _delete_path_and_id(name: str, body: dict) -> tuple[str, str] | None:
    """Return (path_suffix, id) for DELETE, or None if unknown."""
    if name == "worker":
        key = body.get("key")
        return (f"/worker/api/v1/workers/{key}", key) if key else None
    if name == "webhook":
        n = body.get("name")
        return (f"/xray/api/v1/webhooks/{n}", n) if n else None
    if name == "policy":
        n = body.get("name")
        return (f"/xray/api/v1/policies/{n}", n) if n else None
    if name == "watch":
        g = body.get("general_data") or {}
        n = g.get("name")
        return (f"/xray/api/v2/watches/{n}", n) if n else None
    return None


def run_cleanup(
    config_path: str | Path | None = None,
    resources_dir: str | Path | None = None,
    *,
    _client: HttpClient | None = None,
    dry_run: bool = False,
) -> int:
    """Delete Worker, Webhook, Policy, Watch in reverse order of init. Returns 0 if all ok, 1 if any failed.

    Continues with remaining resources when a delete fails (e.g. 404). Uses resource names/keys
    from parsed templates (same as init). If dry_run is True, prints the HTTP method and URL
    for each delete without sending.
    """
    config = load_config(config_path)
    base_url = config["jfrog"]["base_url"].rstrip("/")
    token = get_jfrog_token(config)
    res_dir = _resources_dir(resources_dir)
    client = _client or HttpClient(base_url, token)
    had_failure = False

    for name in CLEANUP_ORDER:
        _, body = load_and_parse_resource(res_dir, name, config)
        pair = _delete_path_and_id(name, body)
        if not pair:
            print(f"Skip {name}: no identifier in body")
            continue
        path, id_val = pair
        full_url = client.url_for(path)
        if dry_run:
            print(f"DELETE {full_url}")
            continue
        try:
            if name == "worker":
                r = delete_worker(client, id_val)
            elif name == "webhook":
                r = delete_webhook(client, id_val)
            elif name == "policy":
                r = delete_policy(client, id_val)
            elif name == "watch":
                r = delete_watch(client, id_val)
            else:
                continue
            status = r.status_code if hasattr(r, "status_code") else getattr(r, "status", 0)
            if status >= 200 and status < 300:
                print(f"Deleted {name} ({id_val}): {status}")
            else:
                print(f"Failed {name} ({id_val}): {status} {getattr(r, 'text', getattr(r, 'content', ''))}")
                had_failure = True
        except Exception as e:
            print(f"Error deleting {name}: {e}")
            had_failure = True
    return 1 if had_failure else 0
