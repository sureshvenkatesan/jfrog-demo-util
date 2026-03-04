"""Run JFrog CLI (jf) subcommands for sync: rt dl, rt u, rt curl."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from shlex import join as shlex_join


def _print_cmd(cmd: list[str]) -> None:
    """Print the command as it would be run (for --verbose)."""
    print("$", shlex_join(cmd))


def jf_available() -> bool:
    """Return True if 'jf' is on PATH."""
    return shutil.which("jf") is not None


def jf_rt_curl(
    server_id: str,
    path: str,
    *,
    method: str = "GET",
    verbose: bool = False,
    insecure_tls: bool = False,
    _run: object | None = None,
) -> subprocess.CompletedProcess:
    """Run: jf rt curl -X <method> <path> --server-id=<id>. Uses --insecure for curl (not --insecure-tls). Returns response body in stdout (e.g. JSON)."""
    cmd = [
        "jf",
        "rt",
        "curl",
        "-X",
        method.upper(),
        path,
        f"--server-id={server_id}",
    ]
    if insecure_tls:
        cmd.append("--insecure")
    if verbose:
        _print_cmd(cmd)
    run = _run or subprocess.run
    return run(cmd, capture_output=True, text=True, timeout=60)


def jf_rt_dl(
    server_id: str,
    source_path: str,
    download_dir: str | Path,
    *,
    verbose: bool = False,
    insecure_tls: bool = False,
    _run: object | None = None,
) -> subprocess.CompletedProcess:
    """Run: jf rt dl <source_path> <download_dir>/ --server-id=<id> (target is 2nd positional)."""
    target = str(download_dir).rstrip("/") + "/"
    cmd = [
        "jf",
        "rt",
        "dl",
        source_path,
        target,
        f"--server-id={server_id}",
    ]
    if verbose:
        cmd.append("--detailed-summary")
    if insecure_tls:
        cmd.append("--insecure-tls")
    if verbose:
        _print_cmd(cmd)
    run = _run or subprocess.run
    env = None
    if verbose:
        env = {**os.environ, "JFROG_CLI_LOG_LEVEL": "DEBUG"}
    return run(cmd, capture_output=True, text=True, timeout=3600, env=env)


def jf_rt_ul(
    server_id: str,
    local_path: str | Path,
    target_repo: str,
    target_path: str = "",
    *,
    verbose: bool = False,
    insecure_tls: bool = False,
    cwd: str | Path | None = None,
    _run: object | None = None,
) -> subprocess.CompletedProcess:
    """Run: jf rt u <local_path_or_pattern> <target_repo>/<target_path> --server-id=<id>.

    If cwd is set, run from that directory so the source pattern is relative and the
    artifact path in the repo does not include the full local filesystem path.
    """
    dest = f"{target_repo}/"
    if target_path:
        dest = f"{target_repo}/{target_path.rstrip('/')}/"
    path_str = str(local_path).rstrip("/")
    # When cwd is set, local_path is relative to cwd - check is_dir under cwd
    if cwd is not None:
        is_dir = (Path(cwd) / path_str).is_dir()
    else:
        is_dir = Path(local_path).is_dir()
    source_pattern = path_str + "/*" if is_dir else path_str
    cmd = [
        "jf",
        "rt",
        "u",
        source_pattern,
        dest,
        f"--server-id={server_id}",
    ]
    if verbose:
        cmd.append("--detailed-summary")
    if insecure_tls:
        cmd.append("--insecure-tls")
    if verbose:
        _print_cmd(cmd)
    run = _run or subprocess.run
    env = None
    if verbose:
        env = {**os.environ, "JFROG_CLI_LOG_LEVEL": "DEBUG"}
    return run(
        cmd,
        capture_output=True,
        text=True,
        timeout=3600,
        env=env,
        cwd=str(cwd) if cwd is not None else None,
    )


def jf_rt_delete(
    server_id: str,
    repo_path: str,
    *,
    verbose: bool = False,
    insecure_tls: bool = False,
    _run: object | None = None,
) -> subprocess.CompletedProcess:
    """Run: jf rt delete <repo_path> --server-id=<id> --quiet --recursive.

    repo_path must be in the form <repository name>/<repository path>, e.g.
    alexsh-generic-local/8d or alexsh-generic-local/path/to/folder.
    """
    cmd = [
        "jf",
        "rt",
        "delete",
        repo_path,
        f"--server-id={server_id}",
        "--quiet",
        "--recursive",
    ]
    if insecure_tls:
        cmd.append("--insecure-tls")
    run = _run or subprocess.run
    env = None
    if verbose:
        env = {**os.environ, "JFROG_CLI_LOG_LEVEL": "DEBUG"}
    return run(cmd, capture_output=True, text=True, timeout=3600, env=env)
