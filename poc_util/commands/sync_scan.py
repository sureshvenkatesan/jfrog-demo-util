"""Trigger Xray index for repo_paths from sync result (jf xr curl api/v2/index)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from poc_util.config import load_config
from poc_util.jf_cli import jf_available, jf_xr_curl

from poc_util.commands.sync_artifacts import SYNC_RESULT_FILENAME

INDEX_API_PATH = "api/v2/index"


def _sync_result_path(config_path: str | Path | None, config: dict) -> Path:
    """Resolve path to sync_result.json using sync.download_dir (same logic as sync)."""
    sync_cfg = config.get("sync")
    if not sync_cfg or not isinstance(sync_cfg, dict):
        raise ValueError("sync section required to resolve sync result path")
    raw_download_dir = sync_cfg.get("download_dir") or "./sync_download"
    download_dir = Path(raw_download_dir)
    if not download_dir.is_absolute():
        config_dir = Path(config_path or "config.yaml").resolve().parent
        download_dir = (config_dir / raw_download_dir).resolve()
    else:
        download_dir = download_dir.resolve()
    return download_dir / SYNC_RESULT_FILENAME


def run_sync_scan(
    config_path: str | Path | None = None,
    *,
    server_id: str | None = None,
    verbose: bool = False,
    insecure_tls: bool = False,
    dry_run: bool = False,
) -> int:
    """Read repo_paths from sync result file and POST each to Xray api/v2/index. Returns 0 on success, 1 on failure."""
    config = load_config(config_path)
    sync_scan = config.get("sync-scan")
    if not sync_scan or not isinstance(sync_scan, dict):
        print("No 'sync-scan' section in config", file=sys.stderr)
        return 1
    effective_server_id = server_id or sync_scan.get("server_id")
    if not effective_server_id:
        print(
            "Server ID required: set sync-scan.server_id in config or pass --server-id",
            file=sys.stderr,
        )
        return 1
    if not jf_available():
        print("jf CLI not found on PATH", file=sys.stderr)
        return 1

    try:
        result_path = _sync_result_path(config_path, config)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    if not result_path.is_file():
        print(
            f"Sync result file not found: {result_path}. Run sync first.",
            file=sys.stderr,
        )
        return 1

    try:
        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Failed to read sync result: {e}", file=sys.stderr)
        return 1

    repo_paths = data.get("repo_paths") if isinstance(data, dict) else None
    if not isinstance(repo_paths, list) or not repo_paths:
        print(
            "Sync result has no repo_paths list or it is empty.",
            file=sys.stderr,
        )
        return 1

    if dry_run:
        for rp in repo_paths:
            print(f"[dry-run] would POST {INDEX_API_PATH} body={json.dumps({'repo_path': rp})}")
        return 0

    failed = []
    for repo_path in repo_paths:
        body = {"repo_path": repo_path}
        result = jf_xr_curl(
            effective_server_id,
            INDEX_API_PATH,
            method="POST",
            body=body,
            verbose=verbose,
            insecure_tls=insecure_tls,
        )
        if verbose and result.stdout:
            print(result.stdout)
        if verbose and result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
        if result.returncode != 0:
            print(
                f"Index request failed for {repo_path}: {result.stderr or result.stdout}",
                file=sys.stderr,
            )
            failed.append(repo_path)
        elif result.stdout:
            try:
                resp = json.loads(result.stdout)
                if isinstance(resp, dict) and resp.get("error"):
                    msg = resp.get("error", "Unknown error")
                    print(
                        f"Index request failed for {repo_path}: {msg}",
                        file=sys.stderr,
                    )
                    failed.append(repo_path)
            except (json.JSONDecodeError, TypeError):
                pass

    if failed:
        print(f"sync-scan failed for {len(failed)} path(s)", file=sys.stderr)
        return 1
    print("sync-scan completed")
    return 0
