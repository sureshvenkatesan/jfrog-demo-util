"""Tests for jf_cli module with mocked subprocess (no real jf execution)."""

from unittest.mock import MagicMock, patch

from poc_util.jf_cli import (
    jf_available,
    jf_rt_curl,
    jf_rt_delete,
    jf_rt_dl,
    jf_rt_ul,
    jf_xr_curl,
)


def test_jf_available_true_when_on_path():
    with patch("poc_util.jf_cli.shutil.which", return_value="/usr/bin/jf"):
        assert jf_available() is True


def test_jf_available_false_when_not_on_path():
    with patch("poc_util.jf_cli.shutil.which", return_value=None):
        assert jf_available() is False


def test_jf_rt_curl_calls_subprocess_with_expected_args():
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
    path = "/api/search/pattern?pattern=repo:*.whl"
    result = jf_rt_curl("my-server", path, _run=mock_run)
    assert result.returncode == 0
    args = mock_run.call_args[0][0]
    assert args[:3] == ["jf", "rt", "curl"]
    assert "-X" in args and "GET" in args
    assert path in args
    assert "--server-id=my-server" in args
    assert "--insecure-tls" not in args


def test_jf_rt_curl_passes_insecure_when_requested():
    """jf rt curl uses --insecure (not --insecure-tls)."""
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
    jf_rt_curl("my-server", "/api/foo", insecure_tls=True, _run=mock_run)
    args = mock_run.call_args[0][0]
    assert "--insecure" in args
    assert "--insecure-tls" not in args


def test_jf_rt_dl_calls_subprocess_with_expected_args(tmp_path):
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    result = jf_rt_dl("my-server", "repo/path/", tmp_path, _run=mock_run)
    assert result.returncode == 0
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0] == "jf"
    assert args[1] == "rt"
    assert args[2] == "dl"
    assert args[3] == "repo/path/"
    assert args[4] == str(tmp_path).rstrip("/") + "/"  # target pattern (2nd positional)
    assert "--server-id=my-server" in args
    assert "--insecure-tls" not in args


def test_jf_rt_dl_passes_insecure_tls_when_requested(tmp_path):
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    jf_rt_dl("my-server", "repo/path/", tmp_path, insecure_tls=True, _run=mock_run)
    args = mock_run.call_args[0][0]
    assert "--insecure-tls" in args


def test_jf_rt_ul_calls_subprocess_with_expected_args(tmp_path):
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    result = jf_rt_ul(
        "target-server", tmp_path, "target-repo", "subpath", _run=mock_run
    )
    assert result.returncode == 0
    args = mock_run.call_args[0][0]
    assert "jf" in args
    assert "rt" in args
    assert args[2] == "u"  # jf rt u (upload)
    assert "target-repo/subpath/" in args or "target-repo/" in args
    assert "--server-id=target-server" in args
    assert "--insecure-tls" not in args


def test_jf_rt_ul_passes_insecure_tls_when_requested(tmp_path):
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    jf_rt_ul("target-server", tmp_path, "target-repo", _run=mock_run, insecure_tls=True)
    args = mock_run.call_args[0][0]
    assert "--insecure-tls" in args


def test_jf_rt_delete_calls_subprocess_with_expected_args():
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    result = jf_rt_delete("my-server", "my-repo/8d", _run=mock_run)
    assert result.returncode == 0
    args = mock_run.call_args[0][0]
    assert args[0] == "jf"
    assert args[1] == "rt"
    assert args[2] == "delete"
    assert args[3] == "my-repo/8d"
    assert "--server-id=my-server" in args
    assert "--quiet" in args
    assert "--recursive" in args
    assert "--insecure-tls" not in args


def test_jf_rt_delete_passes_insecure_tls_when_requested():
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    jf_rt_delete("my-server", "my-repo/path", insecure_tls=True, _run=mock_run)
    args = mock_run.call_args[0][0]
    assert "--insecure-tls" in args


def test_jf_xr_curl_calls_subprocess_with_expected_args():
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
    result = jf_xr_curl(
        "xray-server",
        "api/v1/scanArtifact",
        body={"componentID": "npm://pkg:1.0"},
        _run=mock_run,
    )
    assert result.returncode == 0
    args = mock_run.call_args[0][0]
    assert args[:3] == ["jf", "xr", "curl"]
    assert "-X" in args and "POST" in args
    assert "api/v1/scanArtifact" in args
    assert "--server-id=xray-server" in args
    assert "-H" in args and "Content-Type: application/json" in args
    assert "--data" in args and '{"componentID": "npm://pkg:1.0"}' in args


def test_jf_xr_curl_passes_insecure_tls_when_requested():
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="{}", stderr=""))
    jf_xr_curl("xray-server", "api/v1/foo", body={}, insecure_tls=True, _run=mock_run)
    args = mock_run.call_args[0][0]
    assert "--insecure-tls" in args


def test_jf_xr_curl_verbose_prints_command_including_body():
    """Verbose mode prints the full command including --data body so user sees what is posted."""
    mock_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with patch("poc_util.jf_cli._print_cmd") as mock_print:
        jf_xr_curl("srv", "api/v1/scan", body={"x": 1}, verbose=True, _run=mock_run)
    mock_print.assert_called_once()
    cmd = mock_print.call_args[0][0]
    assert "jf" in cmd and "xr" in cmd and "curl" in cmd
    assert "--data" in cmd and '{"x": 1}' in cmd
