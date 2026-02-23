"""Sync artifacts from source Artifactory to target via jf CLI."""

from __future__ import annotations

from pathlib import Path

from poc_util.config import load_config
from poc_util.jf_cli import jf_available, jf_rt_dl, jf_rt_ul


def run_sync(
    config_path: str | Path | None = None,
    *,
    verbose: bool = False,
    _jf_available: object | None = None,
    _jf_rt_dl: object | None = None,
    _jf_rt_ul: object | None = None,
) -> int:
    """Download from source_path(s) then upload to target. Returns 0 on success, 1 on failure."""
    config = load_config(config_path)
    sync_cfg = config.get("sync")
    if not sync_cfg:
        print("No 'sync' section in config")
        return 1

    available = _jf_available if _jf_available is not None else jf_available
    if not available():
        print("jf CLI not found on PATH")
        return 1

    source_server_id = sync_cfg["source_server_id"]
    source_paths = sync_cfg["source_path"]
    target_server_id = sync_cfg["target_server_id"]
    target_repo = sync_cfg["target_repo"]
    target_path = sync_cfg.get("target_path") or ""
    raw_download_dir = sync_cfg.get("download_dir") or "./sync_download"
    download_dir = Path(raw_download_dir)
    if not download_dir.is_absolute():
        config_dir = Path(config_path or "config.yaml").resolve().parent
        download_dir = (config_dir / raw_download_dir).resolve()
    else:
        download_dir = download_dir.resolve()

    download_dir.mkdir(parents=True, exist_ok=True)
    print(f"Using download_dir from config: {download_dir}")
    dl_fn = _jf_rt_dl or jf_rt_dl
    ul_fn = _jf_rt_ul or jf_rt_ul

    try:
        for sp in source_paths:
            if verbose:
                print(f"\n--- jf rt dl '{sp}' '{download_dir}/' --server-id={source_server_id} --detailed-summary ---")
            result = dl_fn(source_server_id, sp, download_dir, verbose=verbose)
            if verbose:
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
            if result.returncode != 0:
                print(f"Download failed for {sp}: {result.stderr or result.stdout}")
                return 1
        # Upload each top-level entry under download_dir so repo paths are relative (e.g. ch/, jakarta/)
        entries = sorted(download_dir.iterdir()) if download_dir.exists() else []
        if not entries:
            print("No artifacts to upload (download_dir is empty)")
            return 0
        for entry in entries:
            # Dest is repo (and optional target_path) only - jf appends source-relative path,
            # so "8d/*" -> repo/8d/c9/... not repo/8d/8d/c9/...
            repo_prefix = target_path.rstrip("/") if target_path else ""
            if verbose:
                dest = f"{target_repo}/{repo_prefix}/" if repo_prefix else f"{target_repo}/"
                src = f"{entry.name}/*" if entry.is_dir() else entry.name
                print(f"\n--- jf rt u '{src}' '{dest}' --server-id={target_server_id} (cwd={download_dir}) --detailed-summary ---")
            result = ul_fn(
                target_server_id,
                entry.name,
                target_repo,
                repo_prefix,
                verbose=verbose,
                cwd=download_dir,
            )
            if verbose:
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, end="" if result.stderr.endswith("\n") else "\n")
            if result.returncode != 0:
                print(f"Upload failed for {entry.name}: {result.stderr or result.stdout}")
                return 1
        print("Sync completed")
        return 0
    finally:
        # Optionally clean temp dir; leave in place per plan (user may inspect)
        pass
