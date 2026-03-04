"""CLI entrypoint: init and sync subcommands."""

from __future__ import annotations

from pathlib import Path

import click

from poc_util.commands.init_poc import run_cleanup, run_init
from poc_util.commands.sync_artifacts import run_sync, run_sync_cleanup


@click.group()
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=Path("config.yaml"),
    help="Path to config.yaml",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path) -> None:
    """POC utility: init (Worker, Webhook, Policy, Watch) and sync (Artifactory)."""
    ctx.obj = {"config_path": config_path}


@cli.command()
@click.pass_context
@click.option(
    "--resources-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=None,
    help="Directory containing worker.txt, webhook.txt, policy.txt, watch.txt",
)
@click.option(
    "--webhook-delay",
    "webhook_delay_seconds",
    type=float,
    default=2.0,
    help="Seconds to wait after creating webhook before creating policy (so Xray registers the webhook). Use 0 to skip.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show HTTP method and URL for each request without sending.",
)
def init(
    ctx: click.Context,
    resources_dir: Path | None,
    webhook_delay_seconds: float,
    dry_run: bool,
) -> None:
    """Create Worker, Webhook, Policy, and Watch from config and resource templates."""
    config_path = ctx.obj["config_path"]
    code = run_init(
        config_path=config_path,
        resources_dir=resources_dir,
        webhook_delay_seconds=webhook_delay_seconds,
        dry_run=dry_run,
    )
    raise SystemExit(code)


@cli.command()
@click.pass_context
@click.option(
    "--resources-dir",
    type=click.Path(path_type=Path, exists=True, file_okay=False),
    default=None,
    help="Directory containing worker.txt, webhook.txt, policy.txt, watch.txt",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show HTTP method and URL for each delete without sending.",
)
def cleanup(ctx: click.Context, resources_dir: Path | None, dry_run: bool) -> None:
    """Delete Worker, Webhook, Policy, and Watch created by init (reverse order)."""
    config_path = ctx.obj["config_path"]
    code = run_cleanup(
        config_path=config_path,
        resources_dir=resources_dir,
        dry_run=dry_run,
    )
    raise SystemExit(code)


@cli.command()
@click.pass_context
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print jf CLI command lines and their stdout/stderr.",
)
@click.option(
    "--insecure-tls",
    "insecure_tls",
    is_flag=True,
    help="Pass --insecure-tls to jf CLI (skip TLS certificate verification).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Resolve patterns and show files that would be downloaded; do not download or upload.",
)
def sync(ctx: click.Context, verbose: bool, insecure_tls: bool, dry_run: bool) -> None:
    """Download from source Artifactory and upload to target (via jf CLI)."""
    config_path = ctx.obj["config_path"]
    code = run_sync(
        config_path=config_path,
        verbose=verbose,
        insecure_tls=insecure_tls,
        dry_run=dry_run,
    )
    raise SystemExit(code)


@cli.command("sync-cleanup")
@click.pass_context
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print jf CLI command lines and their output.",
)
@click.option(
    "--insecure-tls",
    "insecure_tls",
    is_flag=True,
    help="Pass --insecure-tls to jf CLI (skip TLS certificate verification).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show paths that would be deleted without deleting or prompting.",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt and delete immediately.",
)
def sync_cleanup(
    ctx: click.Context, verbose: bool, insecure_tls: bool, dry_run: bool, yes: bool
) -> None:
    """Delete Artifactory repositories named with the first 2 characters of the uploaded artifact SHA-256."""
    config_path = ctx.obj["config_path"]
    code = run_sync_cleanup(
        config_path=config_path,
        verbose=verbose,
        insecure_tls=insecure_tls,
        dry_run=dry_run,
        yes=yes,
    )
    raise SystemExit(code)


if __name__ == "__main__":
    cli()
