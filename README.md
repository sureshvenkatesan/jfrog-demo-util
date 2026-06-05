# POC Utility -- Terraform

Terraform configuration for spinning up isolated JFrog demo environments on a shared
platform. Each demo gets its own JFrog Project with environment-based local repositories,
remote repositories, a virtual repository, two-tier Xray policies and watches (dry-run
and block), and three Curation policies.

## Architecture

```
poc-util/
├── bootstrap/         # One-time setup: creates the remote state backend repo
├── base/              # Optional: SBOM worker + Xray webhook (disabled by default)
│   └── tests/         # Terraform plan-only tests for the base module
├── demo/              # Per-demo: project, repos, policies, watches, curation
│   └── tests/         # Terraform plan-only tests for the demo module
├── demos/             # Shared credentials + per-demo .tfvars files
└── demo.sh            # Lifecycle script
```

The `demo/` module is the primary entrypoint. The `base/` module is optional and only
needed if you want the SBOM worker and Xray webhook (controlled by
`enable_worker_webhook`, default `false`).

Terraform state is stored **remotely** in a JFrog Artifactory Terraform Backend
repository (`demo-util-tfstate` by default). This provides state locking, encryption
at rest, and team-wide access.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.7
- A JFrog Platform instance with Enterprise X or Enterprise+ license
- A JFrog access token with admin-level permissions
- **Curation**: Remote repositories must be connected to the Curation service before
  curation policies can be applied. This is a one-time platform-level step:
  1. Go to **Administration > Curation > Remote Repositories**
  2. For each package type you use (e.g., npm, pypi), turn on **"Connect current and future"**
  3. This automatically curates all current and future remote repos of that type

## Setup

1. Copy the shared credentials file:

   ```bash
   cp demos/_base.tfvars.example demos/_base.tfvars
   # Edit demos/_base.tfvars with your JFrog URL and access token
   ```

   Alternatively, set credentials via environment variables:

   ```bash
   export TF_VAR_jfrog_url="https://your-instance.jfrog.io"
   export TF_VAR_jfrog_access_token="your-token"
   ```

2. Bootstrap the remote state backend repository (one-time):

   ```bash
   ./demo.sh bootstrap
   ```

   This creates a Terraform Backend repository named `demo-util-tfstate` in your
   Artifactory instance. Override the name with `TF_STATE_REPO` env var if needed.

## Demo Lifecycle

### Create a Demo

1. Create a tfvars file for the demo (see `demos/acme.tfvars.example`):

   ```bash
   cp demos/acme.tfvars.example demos/acme.tfvars
   # Edit with demo-specific settings
   ```

2. Spin it up:

   ```bash
   ./demo.sh create acme
   ```

### Other Commands

```bash
./demo.sh plan acme       # Preview changes
./demo.sh status acme     # Show current state
./demo.sh output acme     # Show Terraform outputs
./demo.sh list            # List all active demos (queries Artifactory)
./demo.sh destroy acme    # Tear down a demo
```

## Optional: SBOM Worker + Webhook

The `base/` module can deploy a shared SBOM worker and Xray webhook. This is
**disabled by default**. To enable it:

1. Add `enable_worker_webhook = true` to `demos/_base.tfvars`
2. Run:

   ```bash
   ./demo.sh init-base
   ```

3. To tear down (only after all demos are destroyed):

   ```bash
   ./demo.sh destroy-base
   ```

## Per-Demo Resources

Each demo creates the following resources, all scoped to a JFrog Project:

| Resource | Terraform Type | Description |
|----------|---------------|-------------|
| JFrog Project | `project` | Isolated project for the demo |
| Curation waiver group | `platform_group` | Decision-owners group for curation waiver requests; auto-named `{demo_name}-curation-waiver` |
| Local repositories | `artifactory_local_<type>_repository` | One per environment × package type (keys: `{demo_name}-{env}-{suffix}`), `xray_index = true` |
| Remote repositories | `artifactory_remote_<type>_repository` | Keys end in `-remote`; `curated = true` when curation is enabled |
| Virtual repositories | `artifactory_virtual_<type>_repository` | One per package type, aggregates matching local + remote repos |
| Dry-run security policy | `xray_security_policy` | Two rules: malicious packages + CVE High (audit only, notify deployer) |
| Block security policy | `xray_security_policy` | Two rules: malicious packages + CVE High (blocks downloads and builds) |
| Dry-run watch | `xray_watch` | Monitors all project repos with the dry-run policy |
| Block watch | `xray_watch` | Monitors all project repos with the block policy |
| Malicious curation policy | `xray_curation_policy` | Blocks malicious packages on remote repos |
| Immature curation policy | `xray_curation_policy` | Blocks immature packages (strict) on remote repos; waiver group as decision owner |
| CVSS 9.0+ curation policy | `xray_curation_policy` | Blocks packages with CVSS score 9.0+ on remote repos; waiver group as decision owner |
| DML Worker (optional) | `platform_workers_service` | Block-if-not-scanned worker |

## Variables

### Shared Credentials (`demos/_base.tfvars`)

| Name | Description |
|------|-------------|
| `jfrog_url` | JFrog Platform base URL |
| `jfrog_access_token` | Admin access token (sensitive) |

### Per-Demo (`demos/<name>.tfvars`)

| Name | Description | Default |
|------|-------------|---------|
| `demo_name` | Short identifier (2-32 chars, lowercase) | *(required)* |
| `environments` | List of environment names for local repos | `["dev", "qa", "prod"]` |
| `local_repos` | Map of suffix to package type (keys must end in `-local`) | `{"generic-local" = "generic"}` |
| `remote_repos` | Map of suffix to upstream URL (keys must end in `-remote`) | `{}` |
| `enable_curation` | Enable curation on remote repos and create curation policies | `true` |
| `curation_malicious_condition_id` | Condition ID for malicious package curation | *(required)* |
| `curation_immature_condition_id` | Condition ID for immature package curation | `"16"` |
| `curation_cvss_condition_id` | Condition ID for CVSS 9.0+ curation | `"3"` |
| `curation_decision_owner_group` | Artifactory group for curation waiver approvals. Leave empty to auto-create `{demo_name}-curation-waiver` | `""` |
| `enable_dml_worker` | Deploy block-if-not-scanned worker | `false` |
| `dml_worker_repo_keys` | Repos the DML worker applies to | `[]` |

### Base Module (optional, `demos/_base.tfvars`)

| Name | Description | Default |
|------|-------------|---------|
| `enable_worker_webhook` | Deploy SBOM worker and Xray webhook | `false` |
| `worker_key` | Worker identifier | `"sbom-service"` |
| `webhook_name` | Webhook name | `"scanCompleted"` |
| `worker_action` | Worker action event type. Default is `AFTER_BUILD_INFO_SAVE`; change to `GENERIC_EVENT` once the `jfrog/platform` provider adds support | `"AFTER_BUILD_INFO_SAVE"` |

## Naming Conventions

- Local repo keys: `{demo_name}-{env}-{suffix}` (e.g., `acme-dev-generic-local`)
- Remote repo keys: `{demo_name}-{suffix}` (e.g., `acme-npm-remote`)
- Virtual repo keys: `{demo_name}-{type}-virtual` (e.g., `acme-npm-virtual`, `acme-pypi-virtual`)
- Security policies: `{demo_name}-dry-run`, `{demo_name}-block`
- Watches: `{demo_name}-dry-run-watch`, `{demo_name}-block-watch`
- Curation policies: `{demo_name}-curation-malicious`, `{demo_name}-curation-immature`, `{demo_name}-curation-cvss-9`

## Testing

Plan-only validation tests live inside each module's `tests/` subdirectory
(`demo/tests/` and `base/tests/`). All providers are mocked so no real
JFrog instance is required.

```bash
# Demo module tests (9 assertions)
terraform -chdir=demo test

# Base module tests (2 assertions)
terraform -chdir=base test
```
