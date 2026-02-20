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
    _run: object | None = None,
) -> subprocess.CompletedProcess:
    """Run: jf rt u <local_path_or_pattern> <target_repo>/<target_path> --server-id=<id>."""
    dest = f"{target_repo}/"
    if target_path:
        dest = f"{target_repo}/{target_path.rstrip('/')}/"
    # Dir: use path/* so contents are uploaded; file: use path as-is
    path = Path(local_path)
    source_pattern = str(local_path).rstrip("/") + "/*" if path.is_dir() else str(local_path)
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
    return run(cmd, capture_output=True, text=True, timeout=3600, env=env)
