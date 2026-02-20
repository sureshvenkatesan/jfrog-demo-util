# POC Utility

CLI to initialize a JFrog POC (Worker, Watch, Policy, Webhook) and sync Artifactory artifacts. Configuration is read from `config.yaml`.

## Commands

- **init** – Create Worker, Webhook, Policy, and Watch from `resources/` templates (worker.txt, webhook.txt, policy.txt, watch.txt) using Python HTTP against Xray and Worker APIs.
- **sync** – Download packages from source Artifactory and upload to target using the JFrog CLI (`jf`). Requires `jf` on PATH and server IDs configured.

## Setup

1. Copy `config.yaml.example` to `config.yaml` and set `jfrog.base_url`, `jfrog.token`, and sync server IDs/paths.
2. For **sync**, install and configure the [JFrog CLI](https://jfrog.com/help/r/jfrog-cli/jfrog-cli) (`jf c add` for source and target).

## Usage

```bash
# From project root (or install the wheel from dist/)
pip install -e .   # or: pip install dist/poc_util-*.whl
poc-util --config config.yaml init
poc-util --config config.yaml sync
```

Optional: `poc-util init --resources-dir /path/to/resources` to use a custom resources directory.

## Build

The project uses [Hatch](https://hatch.pypa.io/) as the package manager and build backend.

```bash
hatch build
# or: ./build.sh
# Output: dist/poc_util-*.whl and dist/poc_util-*.tar.gz
```

The built wheel includes all necessary dependencies as metadata (Requires-Dist in the package’s METADATA), so `pip install dist/poc_util-*.whl` will install the package and its dependencies automatically.

## Testing

Tests mock all external interactions (HTTP to Xray/Worker, `jf` subprocess, config file reads where needed). Run:

```bash
hatch run test
# or with coverage: hatch run test-cov
# or: pip install -e ".[dev]" && pytest tests/ -v
```