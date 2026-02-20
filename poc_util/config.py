"""Load and validate config.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load YAML config from path. Default: config.yaml in cwd."""
    path = Path(config_path or "config.yaml")
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("config.yaml must be a YAML object")
    validate_config(data)
    return data


def validate_config(data: dict[str, Any]) -> None:
    """Validate required sections and fields. Raises ValueError on failure."""
    if "jfrog" not in data:
        raise ValueError("config must have 'jfrog' section")
    jf = data["jfrog"]
    if not isinstance(jf, dict):
        raise ValueError("jfrog must be an object")
    if not jf.get("base_url"):
        raise ValueError("jfrog.base_url is required")
    if not jf.get("token") and not jf.get("access_token"):
        raise ValueError("jfrog.token or jfrog.access_token is required")

    if "init" in data:
        init = data["init"]
        if not isinstance(init, dict):
            raise ValueError("init must be an object")

    if "sync" in data:
        sync = data["sync"]
        if not isinstance(sync, dict):
            raise ValueError("sync must be an object")
        for key in ("source_server_id", "source_path", "target_server_id", "target_repo"):
            if key not in sync:
                raise ValueError(f"sync.{key} is required")
        if not isinstance(sync.get("source_path"), list):
            raise ValueError("sync.source_path must be an array of repo/path strings")


def get_jfrog_token(data: dict[str, Any]) -> str:
    """Return token for API calls (token or access_token)."""
    jf = data["jfrog"]
    return jf.get("token") or jf.get("access_token") or ""


def get_platform_token(data: dict[str, Any]) -> str:
    """Return token for webhook header; defaults to jfrog token."""
    jf = data["jfrog"]
    return jf.get("platform_token") or get_jfrog_token(data)
