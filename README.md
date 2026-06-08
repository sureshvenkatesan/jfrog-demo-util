# POC Utility -- Terraform

Terraform configuration for spinning up isolated JFrog demo environments on a shared
platform. Each demo gets its own JFrog Project with environment-based local repositories,
remote repositories, a virtual repository, two-tier Xray policies and watches (dry-run
and block), and up to fourteen Curation policies (seven DRYRUN + seven BLOCK pairs;
the banned-label pair is optional and requires a custom condition).

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
./demo.sh destroy acme              # Tear down a demo (interactive confirmation)
./demo.sh destroy acme -auto-approve  # Tear down without interactive prompt
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
| Curation DRYRUN policies (×6–7) | `xray_curation_policy` | Audit-only tier for all curated remote repos: MALICIOUS, OPR_IMMATURE, OPR_AGED, CVE_CRITICAL, NO_LICENSE, NO_DOCKERHUB (+ optional BANNED_LABEL) |
| Curation BLOCK policies (×6–7) | `xray_curation_policy` | Enforcement tier scoped to promoted repos: same set as DRYRUN |
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
| `curation_malicious_condition_id` | Condition ID for "Malicious package" | *(required)* |
| `curation_immature_condition_id` | Condition ID for "Package version is immature (permissive)" | `"14"` |
| `curation_aged_condition_id` | Condition ID for "Package version is aged (no newer version)" | `"12"` |
| `curation_critical_condition_id` | Condition ID for "CVE with CVSS ≥ 9 (with or without fix)" | `"3"` |
| `curation_no_license_condition_id` | Condition ID for "Package has no identified license" | `"8"` |
| `curation_no_dockerhub_condition_id` | Condition ID for "Image is not Docker Hub official" | `"17"` |
| `curation_banned_label_condition_id` | Condition ID for a custom banned-label condition (org-specific). Leave empty to skip `CUR_BANNED_LABEL` pair | `""` |
| `curation_decision_owner_group` | Artifactory group for curation waiver approvals. Leave empty to auto-create `{demo_name}-curation-waiver` | `""` |
| `curation_block_repos` | Repo keys to promote from DRYRUN → BLOCK enforcement. Empty = BLOCK covers all repos | `[]` |
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
- Curation policies: `{demo_name}-CUR_{TYPE}_DRYRUN` and `{demo_name}-CUR_{TYPE}_BLOCK` where `{TYPE}` ∈ `MALICIOUS`, `OPR_IMMATURE`, `OPR_AGED`, `CVE_CRITICAL`, `NO_LICENSE`, `NO_DOCKERHUB` (+ optional `BANNED_LABEL`)

## Curation Policies: DRYRUN → BLOCK Promotion

Each demo creates **12 curation policies** (14 when `curation_banned_label_condition_id` is set) in two tiers:

| Policy name | Condition | Condition ID | waiver | Tier |
|---|---|---|---|---|
| `{demo_name}-CUR_MALICIOUS_DRYRUN/BLOCK` | Malicious package | 1 | forbidden | DRYRUN / BLOCK |
| `{demo_name}-CUR_OPR_IMMATURE_DRYRUN/BLOCK` | Package version is immature (permissive) | 14 | forbidden / manual | DRYRUN / BLOCK |
| `{demo_name}-CUR_OPR_AGED_DRYRUN/BLOCK` | Package version is aged (no newer version) | 12 | forbidden / manual | DRYRUN / BLOCK |
| `{demo_name}-CUR_CVE_CRITICAL_DRYRUN/BLOCK` | CVE CVSS ≥ 9 (with or without fix) | 3 | forbidden / manual | DRYRUN / BLOCK |
| `{demo_name}-CUR_NO_LICENSE_DRYRUN/BLOCK` | Package has no identified license | 8 | forbidden / manual | DRYRUN / BLOCK |
| `{demo_name}-CUR_NO_DOCKERHUB_DRYRUN/BLOCK` | Image is not Docker Hub official | 17 | forbidden / manual | DRYRUN / BLOCK |
| `{demo_name}-CUR_BANNED_LABEL_DRYRUN/BLOCK` *(optional)* | Custom banned-label condition | org-specific | forbidden | DRYRUN / BLOCK |

Condition IDs default to the platform-wide built-in values. Override in your `.tfvars` if your instance uses different IDs.

**Default state:** All repos are in DRYRUN (audit) only — violations are logged but not blocked.
BLOCK policies cover `all_repos` when `curation_block_repos` is empty.

### Promote a repo to BLOCK enforcement

Add the repo key to `curation_block_repos` in the demo's `.tfvars` file and re-run `create`:

```hcl
# demos/acme.tfvars
curation_block_repos = ["acme-npm-remote"]
```

```bash
./demo.sh create acme   # re-applies; npm-remote moves to BLOCK scope
```

### Move a repo back to DRYRUN (audit only)

Remove it from `curation_block_repos` and re-apply:

```hcl
# demos/acme.tfvars
curation_block_repos = []   # empty = BLOCK falls back to all_repos scope
```

```bash
./demo.sh create acme
```

> **Note:** Condition IDs are platform-wide integers visible in **Administration > Curation > Conditions**
> or via `./demo.sh list-curation-conditions`. The defaults match the built-in platform conditions:
> malicious=1, immature=14, aged=12, CVE critical=3, no-license=8, no-DockerHub=17.

### Demoing the optional CUR_BANNED_LABEL policy pair

The `CUR_BANNED_LABEL` policy pair uses the **BannedLabels** condition template, which blocks any
package whose metadata carries a specific label. This is useful for showing how a security team can
mark packages as blocked and have them automatically rejected at the proxy layer.

> **Important:** BannedLabels conditions require a pre-registered catalog label. The label `DEMO_BANNED`
> is created automatically via the [JFrog Catalog GraphQL API](https://docs.jfrog.com/security/docs/graphql-apis#create-a-label)
> (`POST /catalog/api/v1/custom/graphql`, mutation `createCustomCatalogLabel`). This is idempotent —
> if the label already exists the call succeeds silently.

#### Automatic setup (recommended)

`./demo.sh create <demo-name>` handles everything automatically:

1. Reads `curation_banned_label_condition_id` from the demo's `.tfvars`.
2. If absent or commented out:
   a. Creates the catalog label `DEMO_BANNED` via GraphQL (idempotent).
   b. Searches for an existing condition named `<demo_name>-banned-label`; reuses it if found.
   c. Otherwise creates the BannedLabels condition using `DEMO_BANNED`.
   d. Writes the condition ID back into the `.tfvars` file.
3. Proceeds with `terraform apply`, creating all **14 policies** (7 DRYRUN + 7 BLOCK).

No manual steps are needed — just run:

```bash
./demo.sh create acme
```

#### Manual setup (optional)

```bash
# List all custom conditions and their IDs
./demo.sh list-curation-conditions

# Create condition "acme-banned-label" using label "acme-banned" (created via GraphQL automatically)
./demo.sh create-curation-condition acme-banned-label
# or override the label explicitly:
./demo.sh create-curation-condition acme-banned-label acme-banned
```

Then set the printed ID in your tfvars before running `create`:

```hcl
# demos/acme.tfvars
curation_banned_label_condition_id = "123"   # ID from list-curation-conditions or create-curation-condition
```

Alternatively, create the label and condition through the UI:
1. Go to **Catalog → Labels → + New Label**, create label `<demo_name>-banned` (e.g. `acme-banned`)
2. Go to **Administration → Curation → Conditions → + New Condition**
3. Select template **Banned Labels**, choose `acme-banned`, and save as `acme-banned-label`
4. Set the condition ID shown in the conditions list in your tfvars

```bash
./demo.sh create acme   # creates CUR_BANNED_LABEL_DRYRUN and CUR_BANNED_LABEL_BLOCK
```

#### Demo the enforcement flow

1. In the Artifactory UI, find any package in `acme-npm-remote` or `acme-docker-remote`
2. Assign the banned label to that package version via
   **Xray → Package Details → Labels** or the Xray properties API
3. Attempt to download it through the remote repo — the BLOCK policy will reject it
4. The DRYRUN policy logs the violation (visible in **Curation → Violations**) without blocking

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
