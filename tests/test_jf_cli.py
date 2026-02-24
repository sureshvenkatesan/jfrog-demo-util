"""Tests for jf_cli module with mocked subprocess (no real jf execution)."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from poc_util.jf_cli import jf_available, jf_rt_delete, jf_rt_dl, jf_rt_ul


def test_jf_available_true_when_on_path():
    with patch("poc_util.jf_cli.shutil.which", return_value="/usr/bin/jf"):
        assert jf_available() is True


def test_jf_available_false_when_not_on_path():
    with patch("poc_util.jf_cli.shutil.which", return_value=None):
        assert jf_available() is False


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
    result = jf_rt_ul("target-server", tmp_path, "target-repo", "subpath", _run=mock_run)
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
