"""Sync artifacts from source Artifactory to target via jf CLI."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from poc_util.api.artifactory import delete_repository
from poc_util.api.client import HttpClient
from poc_util.config import get_jfrog_token, load_config
from poc_util.jf_cli import jf_available, jf_rt_dl, jf_rt_ul


def run_sync(
    config_path: str | Path | None = None,
    *,
    verbose: bool = False,
    insecure_tls: bool = False,
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
            result = dl_fn(source_server_id, sp, download_dir, verbose=verbose, insecure_tls=insecure_tls)
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
                insecure_tls=insecure_tls,
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


def _sha256_prefixes_from_folder(folder: Path) -> list[str]:
    """Collect unique first-2-chars of SHA-256 of every file under folder (recursive)."""
    prefix_set: set[str] = set()
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        prefix = h.hexdigest()[:2]
        prefix_set.add(prefix)
    return sorted(prefix_set)


def run_sync_cleanup(
    config_path: str | Path | None = None,
    *,
    verbose: bool = False,
    insecure_tls: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    _client: HttpClient | None = None,
    _delete_repo: object | None = None,
    _sha256_prefixes_fn: object | None = None,
) -> int:
    """Delete Artifactory repositories named with the first 2 characters of the uploaded artifact SHA-256.

    Repository names to delete are derived from the first two characters of the SHA-256 hash of
    each file in the configurable sync download folder (sync.download_dir). Shows the list, asks
    for confirmation (unless --yes or --dry-run), then deletes via Artifactory API.
    """
    config = load_config(config_path)
    sync_cfg = config.get("sync")
    if not sync_cfg:
        print("No 'sync' section in config")
        return 1

    raw_download_dir = sync_cfg.get("download_dir") or "./sync_download"
    download_dir = Path(raw_download_dir)
    if not download_dir.is_absolute():
        config_dir = Path(config_path or "config.yaml").resolve().parent
        download_dir = (config_dir / raw_download_dir).resolve()
    else:
        download_dir = download_dir.resolve()

    if not download_dir.exists():
        print("No synced artifacts to clean: download_dir does not exist:", download_dir)
        return 0

    prefixes_fn = _sha256_prefixes_fn or _sha256_prefixes_from_folder
    repo_keys = prefixes_fn(download_dir)
    if not repo_keys:
        print("No repositories to delete: no files in download_dir to compute SHA-256 prefixes from.")
        return 0

    print("Repositories to delete (named with first 2 characters of artifact SHA-256):")
    for key in repo_keys:
        print(f"  {key}")
    print(f"Total: {len(repo_keys)} repository(ies)")

    if dry_run:
        print("Dry run: no deletions performed.")
        return 0

    if not yes:
        try:
            reply = input("Delete these repositories? [y/N] ").strip().lower()
        except EOFError:
            reply = "n"
        if reply not in ("y", "yes"):
            print("Aborted.")
            return 0

    base_url = config["jfrog"]["base_url"].rstrip("/")
    token = get_jfrog_token(config)
    verify = not insecure_tls
    client = _client or HttpClient(base_url, token, verify=verify)
    delete_fn = _delete_repo or delete_repository

    failed = []
    for repo_key in repo_keys:
        if verbose:
            print(f"Deleting repository '{repo_key}' ...")
        try:
            resp = delete_fn(client, repo_key)
            if resp.status_code in (200, 204):
                if verbose:
                    print(f"  Deleted {repo_key}")
            elif resp.status_code == 404:
                if verbose:
                    print(f"  {repo_key} not found (already deleted or missing)")
            else:
                print(f"Failed to delete repository '{repo_key}': HTTP {resp.status_code}", file=sys.stderr)
                failed.append(repo_key)
        except Exception as e:
            print(f"Failed to delete repository '{repo_key}': {e}", file=sys.stderr)
            failed.append(repo_key)

    if failed:
        print(f"Sync cleanup completed with errors: {len(failed)} repository(ies) failed.", file=sys.stderr)
        return 1
    print("Sync cleanup completed.")
    return 0
