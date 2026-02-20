"""Tests for init command with mocked HTTP (no real Xray/Worker calls)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poc_util.commands.init_poc import run_init, run_cleanup, INIT_ORDER
from poc_util.api.client import HttpClient


@pytest.fixture
def mock_http_post():
    """Mock requests so no real HTTP is performed."""
    resp = MagicMock()
    resp.status_code = 201
    resp.text = "{}"
    with patch.object(HttpClient, "post", return_value=resp) as m:
        yield m


@pytest.fixture
def config_file(tmp_path, sample_config):
    import yaml
    path = tmp_path / "config.yaml"
    path.write_text(__import__("yaml").dump(sample_config))
    return path


@pytest.fixture
def resources_dir(tmp_path, sample_config):
    """Minimal resource files so parsing succeeds."""
    base = "https://example.jfrog.io"
    for name in INIT_ORDER:
        if name == "worker":
            url = f"{base}/worker/api/v1/workers"
            body = '{"key": "sbom-service", "enabled": true}'
        elif name == "webhook":
            url = f"{base}/xray/api/v1/webhooks"
            body = '{"name": "scanCompleted", "url": "http://w/run", "headers": {"Authorization": "Bearer {platformToken}"}}'
        elif name == "policy":
            url = f"{base}/xray/api/v1/policies"
            body = '{"name": "sbom-policy", "type": "security"}'
        else:
            url = f"{base}/xray/api/v2/watches"
            body = '{"general_data": {"name": "poc-watch"}, "assigned_policies": [{"name": "sbom-policy", "type": "security"}]}'
        (tmp_path / f"{name}.txt").write_text(
            f"curl --location '{url}' \\\n--header 'Content-Type: application/json' \\\n--data '{body}'"
        )
    return tmp_path


def test_run_init_success(config_file, resources_dir, mock_http_post, sample_config):
    """Init runs without real HTTP; all POSTs are mocked."""
    code = run_init(
        config_path=config_file,
        resources_dir=resources_dir,
        webhook_delay_seconds=0,
    )
    assert code == 0
    assert mock_http_post.call_count == 4
    calls = [c[0][1] for c in mock_http_post.call_args_list]
    assert calls[0].get("key") == "sbom-service"
    assert calls[1].get("name") == "scanCompleted"
    assert calls[2].get("name") == "sbom-policy"
    assert calls[3]["general_data"]["name"] == "poc-watch"


def test_run_init_fails_on_http_error(config_file, resources_dir, sample_config):
    """Init returns 1 when API returns non-2xx."""
    resp = MagicMock()
    resp.status_code = 409
    resp.text = "Conflict"
    with patch.object(HttpClient, "post", return_value=resp):
        code = run_init(
            config_path=config_file,
            resources_dir=resources_dir,
            webhook_delay_seconds=0,
        )
    assert code == 1


def test_run_init_fails_on_exception(config_file, resources_dir, sample_config):
    """Init returns 1 when POST raises."""
    with patch.object(HttpClient, "post", side_effect=Exception("network error")):
        code = run_init(
            config_path=config_file,
            resources_dir=resources_dir,
            webhook_delay_seconds=0,
        )
    assert code == 1


def test_run_init_dry_run(config_file, resources_dir, sample_config, capsys):
    """Init with dry_run prints POST URLs and does not call HTTP."""
    with patch.object(HttpClient, "post") as mock_post:
        code = run_init(
            config_path=config_file,
            resources_dir=resources_dir,
            webhook_delay_seconds=0,
            dry_run=True,
        )
    assert code == 0
    assert mock_post.call_count == 0
    out = capsys.readouterr().out
    assert "POST https://example.jfrog.io/worker/api/v1/workers" in out
    assert "POST https://example.jfrog.io/xray/api/v1/webhooks" in out


def test_run_cleanup_success(config_file, resources_dir, sample_config):
    """Cleanup runs DELETE in reverse order; all mocked."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "{}"
    with patch.object(HttpClient, "delete", return_value=resp) as mock_del:
        code = run_cleanup(config_path=config_file, resources_dir=resources_dir)
    assert code == 0
    assert mock_del.call_count == 4
    calls = [c[0][0] for c in mock_del.call_args_list]
    assert calls[0] == "/xray/api/v2/watches/poc-watch"
    assert calls[1] == "/xray/api/v1/policies/sbom-policy"
    assert calls[2] == "/xray/api/v1/webhooks/scanCompleted"
    assert calls[3] == "/worker/api/v1/workers/sbom-service"


def test_run_cleanup_dry_run(config_file, resources_dir, sample_config, capsys):
    """Cleanup with dry_run prints DELETE URLs and does not call HTTP."""
    with patch.object(HttpClient, "delete") as mock_del:
        code = run_cleanup(
            config_path=config_file,
            resources_dir=resources_dir,
            dry_run=True,
        )
    assert code == 0
    assert mock_del.call_count == 0
    out = capsys.readouterr().out
    assert "DELETE https://example.jfrog.io/xray/api/v2/watches/poc-watch" in out
    assert "DELETE https://example.jfrog.io/worker/api/v1/workers/sbom-service" in out


def test_run_cleanup_continues_on_failure(config_file, resources_dir, sample_config):
    """Cleanup tries all deletes and returns 1 when any fails; does not stop on first failure."""
    ok = MagicMock(status_code=200, text="{}")
    fail = MagicMock(status_code=404, text='{"error":"not found"}')
    with patch.object(HttpClient, "delete", side_effect=[fail, ok, ok, ok]) as mock_del:
        code = run_cleanup(config_path=config_file, resources_dir=resources_dir)
    assert code == 1
    assert mock_del.call_count == 4
