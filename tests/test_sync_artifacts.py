"""Tests for sync command with mocked jf CLI (no real subprocess or Artifactory)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poc_util.commands.sync_artifacts import run_sync


@pytest.fixture
def config_file_with_sync(tmp_path, sample_config):
    path = tmp_path / "config.yaml"
    import yaml
    path.write_text(yaml.dump(sample_config))
    return path


def test_run_sync_success(config_file_with_sync, sample_config):
    """Sync runs without real jf; dl and ul are mocked. Upload iterates over download_dir entries."""
    (config_file_with_sync.parent / "sync_download" / "ch").mkdir(parents=True)
    mock_dl = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    mock_ul = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with patch("poc_util.commands.sync_artifacts.jf_available", return_value=True), \
         patch("poc_util.commands.sync_artifacts.jf_rt_dl", mock_dl), \
         patch("poc_util.commands.sync_artifacts.jf_rt_ul", mock_ul):
        code = run_sync(config_path=config_file_with_sync)
    assert code == 0
    assert mock_dl.call_count == 1
    assert mock_ul.call_count == 1
    call_args = mock_dl.call_args[0]
    assert call_args[0] == "source"
    assert call_args[1] == "repo/path/"
    assert isinstance(call_args[2], Path)
    ul_call = mock_ul.call_args[0]
    assert ul_call[2] == "target-repo"
    assert ul_call[3] == ""  # repo prefix empty so path is repo/8d/c9/... not repo/ch/8d/...


def test_run_sync_uses_download_dir_from_config(tmp_path, sample_config):
    """Sync passes config sync.download_dir to jf_rt_dl (resolved relative to config file)."""
    import yaml
    config_path = tmp_path / "config.yaml"
    custom_download = "my_sync_dir"
    sample_config["sync"]["download_dir"] = custom_download
    config_path.write_text(yaml.dump(sample_config))
    (tmp_path / custom_download / "ch").mkdir(parents=True)
    mock_dl = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    mock_ul = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with patch("poc_util.commands.sync_artifacts.jf_available", return_value=True), \
         patch("poc_util.commands.sync_artifacts.jf_rt_dl", mock_dl), \
         patch("poc_util.commands.sync_artifacts.jf_rt_ul", mock_ul):
        code = run_sync(config_path=config_path)
    assert code == 0
    dl_download_dir = mock_dl.call_args[0][2]
    assert dl_download_dir == (tmp_path / custom_download).resolve()
    assert (tmp_path / custom_download).exists()
    ul_call = mock_ul.call_args[0]
    assert ul_call[3] == ""

def test_run_sync_fails_when_jf_not_available(config_file_with_sync):
    with patch("poc_util.commands.sync_artifacts.jf_available", return_value=False):
        code = run_sync(config_path=config_file_with_sync)
    assert code == 1


def test_run_sync_fails_on_download_error(config_file_with_sync):
    mock_dl = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="Download failed"))
    with patch("poc_util.commands.sync_artifacts.jf_available", return_value=True), \
         patch("poc_util.commands.sync_artifacts.jf_rt_dl", mock_dl), \
         patch("poc_util.commands.sync_artifacts.jf_rt_ul", MagicMock()):
        code = run_sync(config_path=config_file_with_sync)
    assert code == 1


def test_run_sync_fails_on_upload_error(config_file_with_sync):
    (config_file_with_sync.parent / "sync_download" / "ch").mkdir(parents=True)
    mock_ul = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="Upload failed"))
    with patch("poc_util.commands.sync_artifacts.jf_available", return_value=True), \
         patch("poc_util.commands.sync_artifacts.jf_rt_dl", return_value=MagicMock(returncode=0)), \
         patch("poc_util.commands.sync_artifacts.jf_rt_ul", mock_ul):
        code = run_sync(config_path=config_file_with_sync)
    assert code == 1


def test_run_sync_passes_insecure_tls_to_jf(config_file_with_sync):
    """When insecure_tls=True, jf_rt_dl and jf_rt_ul are called with insecure_tls=True."""
    (config_file_with_sync.parent / "sync_download" / "ch").mkdir(parents=True)
    mock_dl = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    mock_ul = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with patch("poc_util.commands.sync_artifacts.jf_available", return_value=True), \
         patch("poc_util.commands.sync_artifacts.jf_rt_dl", mock_dl), \
         patch("poc_util.commands.sync_artifacts.jf_rt_ul", mock_ul):
        code = run_sync(config_path=config_file_with_sync, insecure_tls=True)
    assert code == 0
    mock_dl.assert_called()
    mock_ul.assert_called()
    assert mock_dl.call_args[1]["insecure_tls"] is True
    assert mock_ul.call_args[1]["insecure_tls"] is True
