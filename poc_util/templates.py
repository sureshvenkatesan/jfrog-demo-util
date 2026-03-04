"""Parse curl snippets from resource files and substitute config placeholders."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def parse_curl_snippet(content: str) -> tuple[str, dict[str, Any]]:
    """Extract (url, json_body) from a curl command snippet. Raises ValueError on parse error."""
    url = _extract_url(content)
    body_str = _extract_data(content)
    if not body_str:
        raise ValueError("No --data or --data-raw body found in curl snippet")
    # Unescape single quotes used in shell: \' -> '
    body_str = body_str.replace("\\'", "'")
    # Preserve \/ in JSON string values (e.g. regex in TypeScript); json.loads decodes \/ to /,
    # which would break regex literals. Double-escape so decoded value keeps backslash-slash.
    body_str = body_str.replace("\\/", "\\\\/")
    try:
        body = json.loads(body_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in curl data: {e}") from e
    return url, body


def _extract_url(content: str) -> str:
    """Extract URL from curl --location 'URL' or similar."""
    # Match --location 'URL' or --location "URL"
    m = re.search(r"--location\s+['\"]([^'\"]+)['\"]", content, re.IGNORECASE)
    if not m:
        raise ValueError("No --location URL found in curl snippet")
    return m.group(1).strip()


def _extract_data(content: str) -> str:
    """Extract body from first --data or --data-raw single-quoted value."""
    idx_raw = content.find("--data-raw '")
    idx_data = content.find("--data '")
    idx = -1
    if idx_raw != -1 and (idx_data == -1 or idx_raw < idx_data):
        idx = idx_raw
    elif idx_data != -1:
        idx = idx_data
    if idx != -1:
        start = content.index("'", idx) + 1
        return _read_single_quoted(content, start)
    return ""


def _read_single_quoted(s: str, start: int) -> str:
    """Read from start until matching unescaped single quote.
    Handles \\' (backslash-quote = one literal quote) and the shell idiom
    '\\'' (quote backslash quote quote = one literal quote in the middle of a single-quoted string)."""
    i = start
    result = []
    while i < len(s):
        # Shell idiom '\'' (4 chars: quote backslash quote quote) = one literal quote
        if (
            i + 4 <= len(s)
            and s[i] == "'"
            and s[i + 1] == "\\"
            and s[i + 2] == "'"
            and s[i + 3] == "'"
        ):
            result.append("'")
            i += 4
            continue
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "'":
            result.append("'")
            i += 2
            continue
        if s[i] == "'":
            break
        result.append(s[i])
        i += 1
    return "".join(result)


def substitute_in_body(body: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Replace placeholders in body (and nested strings) with config values. Mutates body."""
    token = (
        config.get("jfrog", {}).get("token")
        or config.get("jfrog", {}).get("access_token")
        or ""
    )
    platform_token = config.get("jfrog", {}).get("platform_token") or token

    def replace_in_value(obj: Any) -> Any:
        if isinstance(obj, str):
            s = obj.replace("{platformToken}", platform_token)
            return s
        if isinstance(obj, dict):
            return {k: replace_in_value(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [replace_in_value(v) for v in obj]
        return obj

    return replace_in_value(body)


def substitute_url(url: str, config: dict[str, Any]) -> str:
    """Replace base URL placeholder if present; ensure correct base."""
    base = (config.get("jfrog", {}) or {}).get("base_url", "").rstrip("/")
    if not base:
        return url
    # If URL already has a host, replace the origin with config base
    match = re.match(r"^(https?://[^/]+)(/.*)?$", url)
    if match:
        return base + (match.group(2) or "")
    return url


def load_and_parse_resource(
    resources_dir: Path,
    name: str,
    config: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Load resource file by name (worker, webhook, policy, watch), parse curl, substitute, return (url, body)."""
    path = resources_dir / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Resource file not found: {path}")
    content = path.read_text(encoding="utf-8")
    url, body = parse_curl_snippet(content)
    url = substitute_url(url, config)
    body = substitute_in_body(body, config)
    # Apply init.* overrides from config for names
    init = config.get("init") or {}
    if name == "webhook" and init.get("webhook", {}).get("name"):
        body["name"] = init["webhook"]["name"]
    if name == "webhook" and init.get("webhook", {}).get("url"):
        body["url"] = init["webhook"]["url"]
    if name == "policy" and init.get("policy", {}).get("name"):
        body["name"] = init["policy"]["name"]
    if name == "watch" and init.get("watch", {}).get("name"):
        body.setdefault("general_data", {})["name"] = init["watch"]["name"]
    if name == "watch" and init.get("watch", {}).get("assigned_policies"):
        body["assigned_policies"] = init["watch"]["assigned_policies"]
    if name == "worker" and init.get("worker", {}).get("key"):
        body["key"] = init["worker"]["key"]
    return url, body
