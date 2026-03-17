"""Initiate Xray scan for components from config (jf xr curl api/v1/scanArtifact)."""

from __future__ import annotations

import sys
from pathlib import Path

from poc_util.config import load_config
from poc_util.jf_cli import jf_available, jf_xr_curl

SCAN_ARTIFACT_PATH = "api/v1/scanArtifact"


def run_sync_scan(
    config_path: str | Path | None = None,
    *,
    server_id: str | None = None,
    verbose: bool = False,
    insecure_tls: bool = False,
    dry_run: bool = False,
) -> int:
    """POST each sync-scan component to Xray scanArtifact. Returns 0 on success, 1 on failure."""
    config = load_config(config_path)
    sync_scan = config.get("sync-scan")
    if not sync_scan or not isinstance(sync_scan, dict):
        print("No 'sync-scan' section in config", file=sys.stderr)
        return 1
    components = sync_scan.get("components")
    if not isinstance(components, list) or not components:
        print("sync-scan.components must be a non-empty list", file=sys.stderr)
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
    if dry_run:
        for comp in components:
            body = {"componentID": comp}
            print(f"[dry-run] would POST {SCAN_ARTIFACT_PATH} body={body}")
        return 0
    failed = []
    for comp in components:
        body = {"componentID": comp}
        result = jf_xr_curl(
            effective_server_id,
            SCAN_ARTIFACT_PATH,
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
                f"Scan request failed for {comp}: {result.stderr or result.stdout}",
                file=sys.stderr,
            )
            failed.append(comp)
    if failed:
        print(f"sync-scan failed for {len(failed)} component(s)", file=sys.stderr)
        return 1
    print("sync-scan completed")
    return 0
