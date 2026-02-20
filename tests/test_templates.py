"""Tests for template parsing (mocked file reads)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from poc_util.templates import (
    parse_curl_snippet,
    substitute_in_body,
    substitute_url,
    load_and_parse_resource,
)


def test_parse_curl_snippet_extracts_url_and_body():
    content = """curl --location 'https://example.com/xray/api/v1/webhooks' \\
--header 'Content-Type: application/json' \\
--header 'Authorization: Bearer <jfrog token>' \\
--data '{
    "name": "scanCompleted",
    "url": "http://worker/run",
    "headers": { "Authorization": "Bearer {platformToken}" }
}'"""
    url, body = parse_curl_snippet(content)
    assert url == "https://example.com/xray/api/v1/webhooks"
    assert body["name"] == "scanCompleted"
    assert body["url"] == "http://worker/run"


def test_parse_curl_snippet_data_raw():
    content = """curl --location 'https://x.com/worker/api/v1/workers' \\
--data-raw '{"key": "svc", "enabled": true}'"""
    url, body = parse_curl_snippet(content)
    assert "x.com" in url
    assert body["key"] == "svc"
    assert body["enabled"] is True


def test_parse_curl_snippet_no_data_raises():
    content = """curl --location 'https://example.com/' \\
--header 'Content-Type: application/json'"""
    with pytest.raises(ValueError, match="No --data"):
        parse_curl_snippet(content)


def test_substitute_in_body_replaces_platform_token():
    body = {"headers": {"Authorization": "Bearer {platformToken}"}}
    config = {"jfrog": {"token": "secret", "platform_token": "platform"}}
    out = substitute_in_body(body, config)
    assert out["headers"]["Authorization"] == "Bearer platform"


def test_substitute_url_replaces_origin():
    config = {"jfrog": {"base_url": "https://new.example.com"}}
    url = "https://old.example.com/xray/api/v1/webhooks"
    assert substitute_url(url, config) == "https://new.example.com/xray/api/v1/webhooks"


def test_load_and_parse_resource_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_and_parse_resource(tmp_path, "worker", {})


def test_load_and_parse_resource_injects_init_overrides(tmp_path):
    (tmp_path / "webhook.txt").write_text("""curl --location 'https://x.com/xray/api/v1/webhooks' \\
--header 'Content-Type: application/json' \\
--data '{"name": "old", "url": "http://old"}'""")
    config = {
        "jfrog": {"base_url": "https://cfg.io", "token": "t"},
        "init": {"webhook": {"name": "newName", "url": "http://new"}},
    }
    url, body = load_and_parse_resource(tmp_path, "webhook", config)
    assert body["name"] == "newName"
    assert body["url"] == "http://new"
    assert "cfg.io" in url


# Path to project resources/ (next to tests/)
_RESOURCES_DIR = Path(__file__).resolve().parent.parent / "resources"


def test_worker_resource_parses_and_is_properly_formatted(sample_config):
    """Validate that the real worker.txt parses and sourceCode is fit for the TypeScript compiler.

    Ensures:
    - Worker body has required keys and valid structure.
    - sourceCode preserves escaped slashes in regex literals (\\/ not decoded to /),
      so the API's TypeScript compiler does not see 'Invalid character' at regex lines.
    """
    if not (_RESOURCES_DIR / "worker.txt").is_file():
        pytest.skip("resources/worker.txt not found (e.g. running from installed package only)")

    url, body = load_and_parse_resource(_RESOURCES_DIR, "worker", sample_config)

    assert "key" in body
    assert body.get("key") == "sbom-service"
    assert body.get("application") == "worker"
    assert body.get("enabled") is True
    assert "sourceCode" in body

    source_code = body["sourceCode"]
    assert isinstance(source_code, str)
    assert len(source_code) > 100

    # TypeScript/JS structure
    assert "export default" in source_code or "async" in source_code
    assert "interface" in source_code or "function" in source_code

    # Regex literals must keep escaped slashes so /pattern/ is valid (e.g. /(...)\/CVSS:2\.0\/(.+)/)
    # If \/ were decoded to /, we'd get /(...)/CVSS which closes the regex and causes "Invalid character"
    assert "\\/CVSS" in source_code or "\\/.0" in source_code or "\\/(.+)" in source_code, (
        "sourceCode should preserve \\/ in regex literals for the TypeScript compiler"
    )
    # Escaped dot in regex (e.g. \\.0)
    assert "\\.0" in source_code, (
        "sourceCode should preserve \\. in regex for CVSS pattern"
    )
