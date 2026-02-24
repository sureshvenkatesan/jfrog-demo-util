"""Tests for sync command with mocked jf CLI (no real subprocess or Artifactory)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poc_util.commands.sync_artifacts import run_sync, run_sync_cleanup


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


# --- sync-cleanup ---


def _prefixes(*keys):
    """Return a function that takes a Path and returns the given repo key list (for testing)."""
    def fn(_folder):
        return list(keys)
    return fn


def test_run_sync_cleanup_dry_run_lists_repos_and_exits_without_deleting(config_file_with_sync, capsys):
    """Dry run lists repositories derived from file SHA-256 prefixes and returns 0 without calling API."""
    (config_file_with_sync.parent / "sync_download").mkdir(parents=True)
    code = run_sync_cleanup(
        config_path=config_file_with_sync,
        dry_run=True,
        _sha256_prefixes_fn=_prefixes("8d", "c9"),
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "8d" in out and "c9" in out
    assert "Total: 2 repository(ies)" in out
    assert "first 2 characters" in out or "SHA-256" in out
    assert "Dry run" in out


def test_run_sync_cleanup_repo_keys_derived_from_file_sha256(config_file_with_sync, capsys):
    """Repository names to delete are first 2 chars of SHA-256 of each file in download_dir."""
    dd = config_file_with_sync.parent / "sync_download"
    dd.mkdir(parents=True)
    (dd / "artifact.whl").write_bytes(b"x")  # SHA-256 starts with 2d
    code = run_sync_cleanup(config_path=config_file_with_sync, dry_run=True)
    assert code == 0
    out = capsys.readouterr().out
    assert "2d" in out
    assert "Total: 1 repository(ies)" in out


def test_run_sync_cleanup_yes_deletes_via_api_without_prompt(config_file_with_sync):
    """With yes=True, delete_repository is called for each derived repo key; no input()."""
    (config_file_with_sync.parent / "sync_download").mkdir(parents=True)
    mock_delete = MagicMock(return_value=MagicMock(status_code=204))
    mock_client = MagicMock()
    code = run_sync_cleanup(
        config_path=config_file_with_sync,
        yes=True,
        _client=mock_client,
        _delete_repo=mock_delete,
        _sha256_prefixes_fn=_prefixes("8d"),
    )
    assert code == 0
    assert mock_delete.call_count == 1
    assert mock_delete.call_args[0][1] == "8d"


def test_run_sync_cleanup_aborts_when_user_says_no(config_file_with_sync, capsys):
    """When user answers non-yes, no delete is performed."""
    (config_file_with_sync.parent / "sync_download").mkdir(parents=True)
    with patch("builtins.input", return_value="n"):
        code = run_sync_cleanup(
            config_path=config_file_with_sync,
            yes=False,
            _sha256_prefixes_fn=_prefixes("8d"),
        )
    assert code == 0
    out = capsys.readouterr().out
    assert "Aborted" in out


def test_run_sync_cleanup_no_download_dir_exits_0(config_file_with_sync, capsys):
    """When download_dir does not exist, exit 0 and message."""
    code = run_sync_cleanup(config_path=config_file_with_sync)
    assert code == 0
    out = capsys.readouterr().out
    assert "does not exist" in out or "No synced" in out


def test_run_sync_cleanup_no_files_in_download_dir_exits_0(config_file_with_sync, capsys):
    """When download_dir has no files, exit 0 and message (no SHA-256 prefixes)."""
    (config_file_with_sync.parent / "sync_download").mkdir(parents=True)
    code = run_sync_cleanup(config_path=config_file_with_sync)
    assert code == 0
    out = capsys.readouterr().out
    assert "No repositories to delete" in out or "no files" in out


def test_run_sync_cleanup_returns_1_when_delete_fails(config_file_with_sync):
    """When Artifactory API returns non-2xx (and not 404), cleanup returns 1."""
    (config_file_with_sync.parent / "sync_download").mkdir(parents=True)
    mock_delete = MagicMock(return_value=MagicMock(status_code=500))
    code = run_sync_cleanup(
        config_path=config_file_with_sync,
        yes=True,
        _client=MagicMock(),
        _delete_repo=mock_delete,
        _sha256_prefixes_fn=_prefixes("8d"),
    )
    assert code == 1


def test_run_sync_cleanup_passes_insecure_tls_to_client(config_file_with_sync):
    """When insecure_tls=True, HttpClient is created with verify=False."""
    (config_file_with_sync.parent / "sync_download").mkdir(parents=True)
    with patch("poc_util.commands.sync_artifacts.HttpClient") as mock_http_class:
        mock_delete = MagicMock(return_value=MagicMock(status_code=204))
        run_sync_cleanup(
            config_path=config_file_with_sync,
            yes=True,
            insecure_tls=True,
            _delete_repo=mock_delete,
            _sha256_prefixes_fn=_prefixes("8d"),
        )
        mock_http_class.assert_called_once()
        assert mock_http_class.call_args[1]["verify"] is False
