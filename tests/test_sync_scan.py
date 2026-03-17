"""Tests for sync-scan command with mocked jf CLI (no real Xray calls)."""

import yaml
from unittest.mock import MagicMock, patch

import pytest

from poc_util.commands.sync_scan import run_sync_scan


@pytest.fixture
def config_with_sync_scan(tmp_path):
    """Config that includes valid sync-scan section."""
    config = {
        "jfrog": {"base_url": "https://example.jfrog.io", "token": "t"},
        "sync-scan": {
            "server_id": "xray-server",
            "components": ["npm://lodash:4.17.21", "npm://express:4.18.2"],
        },
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return path


def test_run_sync_scan_success(config_with_sync_scan):
    """Sync-scan runs jf xr curl for each component and returns 0 when all succeed."""
    mock_curl = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
    with (
        patch("poc_util.commands.sync_scan.jf_available", return_value=True),
        patch("poc_util.commands.sync_scan.jf_xr_curl", mock_curl),
    ):
        code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 0
    assert mock_curl.call_count == 2
    calls = [mock_curl.call_args_list[i][0] for i in range(2)]
    assert calls[0][1] == "api/v1/scanArtifact"
    assert mock_curl.call_args_list[0][1]["body"] == {
        "componentID": "npm://lodash:4.17.21"
    }
    assert mock_curl.call_args_list[1][1]["body"] == {
        "componentID": "npm://express:4.18.2"
    }


def test_run_sync_scan_dry_run_exits_0_without_calling_curl(
    config_with_sync_scan, capsys
):
    """With dry_run=True, sync-scan prints requests and does not call jf xr curl."""
    with (
        patch("poc_util.commands.sync_scan.jf_available", return_value=True),
        patch("poc_util.commands.sync_scan.jf_xr_curl", MagicMock()) as mock_curl,
    ):
        code = run_sync_scan(config_path=config_with_sync_scan, dry_run=True)
    assert code == 0
    mock_curl.assert_not_called()
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "lodash" in out and "express" in out


def test_run_sync_scan_uses_server_id_from_cli(config_with_sync_scan):
    """--server-id overrides config sync-scan.server_id."""
    mock_curl = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with (
        patch("poc_util.commands.sync_scan.jf_available", return_value=True),
        patch("poc_util.commands.sync_scan.jf_xr_curl", mock_curl),
    ):
        run_sync_scan(
            config_path=config_with_sync_scan,
            server_id="cli-override",
        )
    mock_curl.assert_called()
    assert mock_curl.call_args[0][0] == "cli-override"


def test_run_sync_scan_no_section_returns_1(tmp_path, capsys):
    """When config has no sync-scan section, returns 1 and prints error."""
    config = {"jfrog": {"base_url": "https://x.io", "token": "t"}}
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    code = run_sync_scan(config_path=path)
    assert code == 1
    assert "No 'sync-scan' section" in capsys.readouterr().err


def test_run_sync_scan_empty_components_raises_at_load(tmp_path):
    """When sync-scan.components is empty, config validation raises ValueError."""
    config = {
        "jfrog": {"base_url": "https://x.io", "token": "t"},
        "sync-scan": {"server_id": "srv", "components": []},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    with pytest.raises(ValueError, match="non-empty array"):
        run_sync_scan(config_path=path)


def test_run_sync_scan_no_server_id_returns_1(tmp_path, capsys):
    """When sync-scan has no server_id and no CLI --server-id, returns 1."""
    config = {
        "jfrog": {"base_url": "https://x.io", "token": "t"},
        "sync-scan": {"components": ["npm://pkg:1.0"]},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    code = run_sync_scan(config_path=path)
    assert code == 1
    assert "Server ID required" in capsys.readouterr().err


def test_run_sync_scan_jf_not_available_returns_1(config_with_sync_scan, capsys):
    """When jf is not on PATH, returns 1."""
    with patch("poc_util.commands.sync_scan.jf_available", return_value=False):
        code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 1
    assert "jf CLI not found" in capsys.readouterr().err


def test_run_sync_scan_returns_1_when_curl_fails(config_with_sync_scan, capsys):
    """When jf xr curl returns non-zero, sync-scan returns 1."""
    mock_curl = MagicMock(
        return_value=MagicMock(returncode=1, stdout="", stderr="Xray error")
    )
    with (
        patch("poc_util.commands.sync_scan.jf_available", return_value=True),
        patch("poc_util.commands.sync_scan.jf_xr_curl", mock_curl),
    ):
        code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 1
    assert "failed" in capsys.readouterr().err


def test_run_sync_scan_passes_verbose_and_insecure_tls(config_with_sync_scan):
    """verbose and insecure_tls are passed to jf_xr_curl."""
    mock_curl = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with (
        patch("poc_util.commands.sync_scan.jf_available", return_value=True),
        patch("poc_util.commands.sync_scan.jf_xr_curl", mock_curl),
    ):
        run_sync_scan(
            config_path=config_with_sync_scan,
            verbose=True,
            insecure_tls=True,
        )
    for call in mock_curl.call_args_list:
        assert call[1]["verbose"] is True
        assert call[1]["insecure_tls"] is True
