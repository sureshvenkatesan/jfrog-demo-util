"""Tests for CLI entrypoint (mocked config and commands)."""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from poc_util.cli import cli


@pytest.fixture
def config_file(tmp_path, sample_config):
    import yaml

    path = tmp_path / "config.yaml"
    path.write_text(yaml.dump(sample_config))
    return path


def test_cli_init_invokes_run_init(config_file, sample_config):
    with patch("poc_util.cli.run_init", return_value=0) as mock_init:
        result = CliRunner().invoke(cli, ["--config", str(config_file), "init"])
    assert result.exit_code == 0
    mock_init.assert_called_once()
    call_kw = mock_init.call_args[1]
    assert str(call_kw["config_path"]) == str(config_file)


def test_cli_sync_invokes_run_sync(config_file):
    with patch("poc_util.cli.run_sync", return_value=0) as mock_sync:
        result = CliRunner().invoke(cli, ["--config", str(config_file), "sync"])
    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kw = mock_sync.call_args[1]
    assert call_kw["dry_run"] is False


def test_cli_sync_dry_run_passes_flag(config_file):
    with patch("poc_util.cli.run_sync", return_value=0) as mock_sync:
        result = CliRunner().invoke(
            cli, ["--config", str(config_file), "sync", "--dry-run"]
        )
    assert result.exit_code == 0
    mock_sync.assert_called_once()
    call_kw = mock_sync.call_args[1]
    assert call_kw["dry_run"] is True


def test_cli_sync_cleanup_invokes_run_sync_cleanup(config_file):
    with patch("poc_util.cli.run_sync_cleanup", return_value=0) as mock_cleanup:
        result = CliRunner().invoke(
            cli, ["--config", str(config_file), "sync-cleanup", "--yes"]
        )
    assert result.exit_code == 0
    mock_cleanup.assert_called_once()
    call_kw = mock_cleanup.call_args[1]
    assert call_kw["yes"] is True


def test_cli_sync_scan_invokes_run_sync_scan(config_file):
    """Config in conftest may not have sync-scan; we only check that run_sync_scan is invoked."""
    with patch("poc_util.cli.run_sync_scan", return_value=0) as mock_scan:
        result = CliRunner().invoke(cli, ["--config", str(config_file), "sync-scan"])
    assert result.exit_code == 0
    mock_scan.assert_called_once()
    call_kw = mock_scan.call_args[1]
    assert call_kw["server_id"] is None
    assert call_kw["verbose"] is False


def test_cli_sync_scan_passes_server_id_and_verbose(config_file):
    with patch("poc_util.cli.run_sync_scan", return_value=0) as mock_scan:
        result = CliRunner().invoke(
            cli,
            [
                "--config",
                str(config_file),
                "sync-scan",
                "--server-id",
                "my-xray",
                "--verbose",
            ],
        )
    assert result.exit_code == 0
    call_kw = mock_scan.call_args[1]
    assert call_kw["server_id"] == "my-xray"
    assert call_kw["verbose"] is True
