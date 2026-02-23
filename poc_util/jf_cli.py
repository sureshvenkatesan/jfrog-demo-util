"""Run JFrog CLI (jf) subcommands for sync: rt dl, rt u."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def jf_available() -> bool:
    """Return True if 'jf' is on PATH."""
    return shutil.which("jf") is not None


def jf_rt_dl(
    server_id: str,
    source_path: str,
    download_dir: str | Path,
    *,
    verbose: bool = False,
    _run: object | None = None,
) -> subprocess.CompletedProcess:
    """Run: jf rt dl <source_path> <download_dir>/ --server-id=<id> (target is 2nd positional)."""
    target = str(download_dir).rstrip("/") + "/"
    cmd = [
        "jf", "rt", "dl",
        source_path,
        target,
        f"--server-id={server_id}",
    ]
    if verbose:
        cmd.append("--detailed-summary")
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
        "jf", "rt", "u",
        source_pattern,
        dest,
        f"--server-id={server_id}",
    ]
    if verbose:
        cmd.append("--detailed-summary")
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
