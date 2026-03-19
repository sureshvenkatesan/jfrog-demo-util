"""Tests for sync-scan command (reads sync_result.json, POSTs api/v2/index)."""

import json
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poc_util.commands.sync_scan import run_sync_scan, SYNC_RESULT_FILENAME


@pytest.fixture
def config_with_sync_scan(tmp_path):
    """Config with sync and sync-scan; sync_result.json will be placed in sync.download_dir."""
    config = {
        "jfrog": {"base_url": "https://example.jfrog.io", "token": "t"},
        "sync": {
            "source_server_id": "src",
            "source_patterns": ["repo:*"],
            "target_server_id": "tgt",
            "target_repo": "target-repo",
            "download_dir": "./sync_download",
        },
        "sync-scan": {"server_id": "xray-server"},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    return path


@pytest.fixture
def sync_result_file(config_with_sync_scan):
    """Create sync_result.json in sync download_dir with two repo_paths."""
    config_dir = config_with_sync_scan.parent
    download_dir = config_dir / "sync_download"
    download_dir.mkdir(parents=True, exist_ok=True)
    result_path = download_dir / SYNC_RESULT_FILENAME
    result_path.write_text(
        json.dumps({"repo_paths": ["target-repo/a.whl", "target-repo/b.tar"]})
    )
    return result_path


def test_run_sync_scan_success(config_with_sync_scan, sync_result_file):
    """Sync-scan reads sync_result.json and POSTs api/v2/index for each repo_path."""
    mock_curl = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
    with (
        patch("poc_util.commands.sync_scan.jf_available", return_value=True),
        patch("poc_util.commands.sync_scan.jf_xr_curl", mock_curl),
    ):
        code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 0
    assert mock_curl.call_count == 2
    assert mock_curl.call_args_list[0][0][1] == "api/v2/index"
    assert mock_curl.call_args_list[0][1]["body"] == {"repo_path": "target-repo/a.whl"}
    assert mock_curl.call_args_list[1][1]["body"] == {"repo_path": "target-repo/b.tar"}


def test_run_sync_scan_dry_run_exits_0_without_calling_curl(
    config_with_sync_scan, sync_result_file, capsys
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
    assert "target-repo/a.whl" in out and "target-repo/b.tar" in out


def test_run_sync_scan_uses_server_id_from_cli(config_with_sync_scan, sync_result_file):
    """--server-id overrides config sync-scan.server_id."""
    mock_curl = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
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


def test_run_sync_scan_no_sync_section_returns_1(tmp_path, capsys):
    """When config has sync-scan but no sync section, returns 1 (cannot resolve result path)."""
    config = {
        "jfrog": {"base_url": "https://x.io", "token": "t"},
        "sync-scan": {"server_id": "srv"},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    code = run_sync_scan(config_path=path)
    assert code == 1
    assert "sync" in capsys.readouterr().err.lower()


def test_run_sync_scan_no_server_id_returns_1(tmp_path, capsys):
    """When sync-scan has empty server_id and no CLI --server-id, returns 1."""
    config = {
        "jfrog": {"base_url": "https://x.io", "token": "t"},
        "sync": {
            "source_server_id": "a",
            "source_patterns": ["r:*"],
            "target_server_id": "b",
            "target_repo": "r",
            "download_dir": "./sync_download",
        },
        "sync-scan": {"server_id": ""},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(config))
    (tmp_path / "sync_download").mkdir()
    (tmp_path / "sync_download" / SYNC_RESULT_FILENAME).write_text(
        json.dumps({"repo_paths": ["r/x"]})
    )
    code = run_sync_scan(config_path=path)
    assert code == 1
    assert "Server ID required" in capsys.readouterr().err


def test_run_sync_scan_missing_result_file_returns_1(config_with_sync_scan, capsys):
    """When sync_result.json does not exist, returns 1 and tells user to run sync first."""
    # Do not create sync_result_file; only config exists
    (config_with_sync_scan.parent / "sync_download").mkdir(parents=True, exist_ok=True)
    code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 1
    err = capsys.readouterr().err
    assert "not found" in err or "Run sync first" in err


def test_run_sync_scan_empty_repo_paths_returns_1(config_with_sync_scan, capsys):
    """When sync result has empty repo_paths, returns 1."""
    download_dir = config_with_sync_scan.parent / "sync_download"
    download_dir.mkdir(parents=True, exist_ok=True)
    (download_dir / SYNC_RESULT_FILENAME).write_text(json.dumps({"repo_paths": []}))
    code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 1
    assert "no repo_paths" in capsys.readouterr().err or "empty" in capsys.readouterr().err


def test_run_sync_scan_jf_not_available_returns_1(config_with_sync_scan, sync_result_file, capsys):
    """When jf is not on PATH, returns 1."""
    with patch("poc_util.commands.sync_scan.jf_available", return_value=False):
        code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 1
    assert "jf CLI not found" in capsys.readouterr().err


def test_run_sync_scan_returns_1_when_curl_fails(config_with_sync_scan, sync_result_file, capsys):
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


def test_run_sync_scan_returns_1_when_response_has_error_key(
    config_with_sync_scan, sync_result_file, capsys
):
    """When response JSON has 'error' key, sync-scan returns 1."""
    mock_curl = MagicMock(
        return_value=MagicMock(
            returncode=0,
            stdout='{"error":"Failed to index"}',
            stderr="",
        )
    )
    with (
        patch("poc_util.commands.sync_scan.jf_available", return_value=True),
        patch("poc_util.commands.sync_scan.jf_xr_curl", mock_curl),
    ):
        code = run_sync_scan(config_path=config_with_sync_scan)
    assert code == 1
    err = capsys.readouterr().err
    assert "Failed to index" in err


def test_run_sync_scan_passes_verbose_and_insecure_tls(
    config_with_sync_scan, sync_result_file
):
    """verbose and insecure_tls are passed to jf_xr_curl."""
    mock_curl = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
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
