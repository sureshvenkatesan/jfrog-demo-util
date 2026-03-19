"""Sync artifacts from source Artifactory to target via jf CLI."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import urlencode

from poc_util.api.artifactory import delete_repository
from poc_util.api.client import HttpClient
from poc_util.config import get_jfrog_token, load_config
from poc_util.jf_cli import jf_available, jf_rt_curl, jf_rt_dl, jf_rt_ul

SYNC_RESULT_FILENAME = "sync_result.json"


def _pattern_search_via_jf(
    server_id: str, pattern: str, insecure_tls: bool, verbose: bool = False
) -> dict:
    """Run pattern search via jf rt curl; return JSON with repoUri, sourcePattern, files."""
    path = "/api/search/pattern?" + urlencode({"pattern": pattern})
    result = jf_rt_curl(server_id, path, insecure_tls=insecure_tls, verbose=verbose)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "jf rt curl failed")
    return json.loads(result.stdout)


def _resolve_patterns_to_paths(
    patterns: list[str],
    source_server_id: str,
    insecure_tls: bool,
    verbose: bool = False,
) -> list[str]:
    """Resolve patterns via jf rt curl (Artifactory pattern search); return flat list of repo/path strings."""
    paths: list[str] = []
    for pattern in patterns:
        data = _pattern_search_via_jf(
            source_server_id, pattern, insecure_tls, verbose=verbose
        )
        repo_uri = data.get("repoUri") or ""
        source_pattern = data.get("sourcePattern") or ""
        files = data.get("files") or []
        # Repo key: from sourcePattern (part before ":") or from repoUri (last path segment)
        if ":" in source_pattern:
            repo = source_pattern.split(":", 1)[0]
        else:
            repo = repo_uri.rstrip("/").split("/")[-1] if repo_uri else ""
        for f in files:
            paths.append(f"{repo}/{f}")
    return paths


def _uploaded_repo_paths(
    download_dir: Path,
    entries: list[Path],
    target_repo: str,
    target_path: str,
) -> list[str]:
    """Build list of repo_path strings for every file that was (or will be) uploaded.

    Each repo_path uses sync.target_repo as the repository (e.g. repo_key/path/to/file).
    """
    # prefix is sync.target_repo [+ optional target_path]
    prefix = f"{target_repo}/{target_path.rstrip('/')}".rstrip("/") if target_path else target_repo
    repo_paths: list[str] = []
    for entry in entries:
        if entry.is_file():
            repo_paths.append(f"{prefix}/{entry.name}")
        else:
            for p in entry.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(entry)
                    repo_paths.append(f"{prefix}/{entry.name}/{rel.as_posix()}")
    return repo_paths


def run_sync(
    config_path: str | Path | None = None,
    *,
    verbose: bool = False,
    insecure_tls: bool = False,
    dry_run: bool = False,
    _jf_available: object | None = None,
    _jf_rt_dl: object | None = None,
    _jf_rt_ul: object | None = None,
) -> int:
    """Resolve source_patterns via jf rt curl (Artifactory pattern search), then download and upload to target. Returns 0 on success, 1 on failure."""
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
    source_patterns = sync_cfg["source_patterns"]
    source_paths = _resolve_patterns_to_paths(
        source_patterns, source_server_id, insecure_tls, verbose=verbose
    )
    if not source_paths:
        print("No artifacts matched any source pattern")
        return 0

    if dry_run:
        print("Dry run: resolved patterns (files that would be downloaded):")
        for p in source_paths:
            print(f"  {p}")
        print(
            f"Total: {len(source_paths)} file(s) from {len(source_patterns)} pattern(s)"
        )
        return 0

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
    if verbose:
        print(
            f"Resolved {len(source_paths)} artifact(s) from {len(source_patterns)} pattern(s)"
        )
    dl_fn = _jf_rt_dl or jf_rt_dl
    ul_fn = _jf_rt_ul or jf_rt_ul

    try:
        for sp in source_paths:
            result = dl_fn(
                source_server_id,
                sp,
                download_dir,
                verbose=verbose,
                insecure_tls=insecure_tls,
            )
            if verbose:
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(
                        result.stderr, end="" if result.stderr.endswith("\n") else "\n"
                    )
            if result.returncode != 0:
                print(f"Download failed for {sp}: {result.stderr or result.stdout}")
                return 1
        # Upload each top-level entry under download_dir (exclude sync result file)
        all_entries = sorted(download_dir.iterdir()) if download_dir.exists() else []
        entries = [e for e in all_entries if e.name != SYNC_RESULT_FILENAME]
        if not entries:
            print("No artifacts to upload (download_dir is empty)")
            return 0
        for entry in entries:
            # Dest is repo (and optional target_path) only - jf appends source-relative path,
            # so "8d/*" -> repo/8d/c9/... not repo/8d/8d/c9/...
            repo_prefix = target_path.rstrip("/") if target_path else ""
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
                    print(
                        result.stderr, end="" if result.stderr.endswith("\n") else "\n"
                    )
            if result.returncode != 0:
                print(
                    f"Upload failed for {entry.name}: {result.stderr or result.stdout}"
                )
                return 1
        # repo_paths must use sync.target_repo as the repository for each path
        repo_paths = _uploaded_repo_paths(
            download_dir, entries, target_repo, target_path
        )
        result_path = download_dir / SYNC_RESULT_FILENAME
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump({"repo_paths": repo_paths}, f, indent=2)
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
        print(
            "No synced artifacts to clean: download_dir does not exist:", download_dir
        )
        return 0

    prefixes_fn = _sha256_prefixes_fn or _sha256_prefixes_from_folder
    repo_keys = prefixes_fn(download_dir)
    if not repo_keys:
        print(
            "No repositories to delete: no files in download_dir to compute SHA-256 prefixes from."
        )
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
                print(
                    f"Failed to delete repository '{repo_key}': HTTP {resp.status_code}",
                    file=sys.stderr,
                )
                failed.append(repo_key)
        except Exception as e:
            print(f"Failed to delete repository '{repo_key}': {e}", file=sys.stderr)
            failed.append(repo_key)

    if failed:
        print(
            f"Sync cleanup completed with errors: {len(failed)} repository(ies) failed.",
            file=sys.stderr,
        )
        return 1
    print("Sync cleanup completed.")
    return 0
