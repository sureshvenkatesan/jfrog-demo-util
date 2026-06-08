# Changes — preRelease/sureshv (2026-06-04)

All changes are on the `preRelease/sureshv` branch (based on `terraform-impl`).

---

## 1. Branch setup

- Created `preRelease/sureshv` from the latest `github-sv/terraform-impl` remote branch.

---

## 2. Fix: curation policy group does not exist in Artifactory

**Error:** `./demo.sh create acme` failed with:
```
policy is invalid: group "Chaitanya-CurationWaiver-Demo" does not exist in artifactory
```

**Root cause:** `curation_decision_owner_group` was hardcoded to `"Chaitanya-CurationWaiver-Demo"` as the variable default. The group was never created in Artifactory, so both `xray_curation_policy.immature` and `xray_curation_policy.cvss` failed on create.

**Changes (`demo/main.tf`, `demo/variables.tf`):**

- Added `local.curation_group_name = coalesce(var.curation_decision_owner_group, "${var.demo_name}-curation-waiver")` — auto-derives a sensible name from `demo_name` when the variable is left empty.
- Added `resource "platform_group" "curation_waiver"` (`count = enable_curation ? 1 : 0`) — creates the decision-owners group in Artifactory as part of the demo. Uses the non-deprecated `platform` provider (not `artifactory_group`).
- Updated `decision_owners` in both curation policies to reference `local.curation_group_name` and added `platform_group.curation_waiver` to their `depends_on`.
- Changed `curation_decision_owner_group` default from `"Chaitanya-CurationWaiver-Demo"` to `""`, triggering the `coalesce` fallback.

---

## 3. Fix: Terraform tests were not discoverable or passing

**Error:** `terraform test -test-directory=../tests` returned `"Invalid testing directory"` (Terraform forbids `..` paths). All nine demo tests and two base tests were failing.

**Changes:**

- Moved `tests/demo.tftest.hcl` → `demo/tests/demo.tftest.hcl`
- Moved `tests/base.tftest.hcl` → `base/tests/base.tftest.hcl`
- Deleted the now-empty root-level `tests/` directory.
- Added `mock_provider` blocks for all four providers (`artifactory`, `xray`, `project`, `platform`) to both test files — providers were calling the JFrog API at plan time even for a fake URL, failing with "could not parse version".
- Bumped `required_version` from `>= 1.6` → `>= 1.7` in both `demo/providers.tf` and `base/providers.tf` (`mock_provider` requires Terraform 1.7+).
- **Bug fix (`demo/main.tf`):** `xray_watch.block` had `active = false` (copy-paste error); fixed to `true`.
- **Bug fix (`base/main.tf`):** `platform_workers_service.sbom` was missing the required `filter_criteria` block; added with `artifact_filter_criteria { repo_keys = [] }`.
- **Bug fix (`base/main.tf`, `base/variables.tf`):** `action = "GENERIC_EVENT"` is not in the `jfrog/platform` provider's schema validation (provider limitation as of v2.2.10). Replaced with a configurable `var.worker_action` defaulting to `"AFTER_BUILD_INFO_SAVE"`, with validation and documentation noting the provider gap.

**Result:** 9/9 demo tests pass, 2/2 base tests pass — all offline with mocked providers.

---

## 4. Fix: README testing instructions were stale

Updated `README.md` testing section: replaced the invalid `-test-directory=../tests` flag with the correct `terraform -chdir=demo test` / `terraform -chdir=base test` commands. Added note that all providers are mocked (no real JFrog instance required).

---

## 5. Fix: `./demo.sh list` always showed "No active demos."

**Root cause (two bugs in `cmd_list_quiet`):**

- **Bug 1:** Storage API URL was `${JFROG_URL}/api/storage/…` — missing `/artifactory` prefix. The curl silently returned empty (`|| return 0`).
- **Bug 2:** curl used `-u "_:${JFROG_TOKEN}"` — the `_` placeholder username is rejected by this Artifactory instance with `401 "Wrong username was used"`. Fixed to use `${TF_HTTP_USERNAME}` (set by `parse_jfrog_creds`).
- **Bug 3 (discovered later):** When the state repo has no children, `grep` returns exit code 1, which `set -euo pipefail` treats as a fatal error — the script exited silently. Fixed by capturing grep output with `|| true` and early-returning on empty results.

---

## 6. Fix: `./demo.sh destroy acme` failed with "Project containing resources can't be removed"

**Root cause:** JFrog automatically creates a `{demo_name}-build-info` local repository whenever a JFrog Project is provisioned. This repo is:
- Not managed by Terraform (no resource for it)
- Locked to the project (cannot be detached or deleted independently)
- Blocking the standard `DELETE /access/api/v1/projects/{key}` API

The only way to delete the project _and_ its build-info repo is:
```
DELETE /access/api/v1/projects/{key}?deleteRepos=true
```

**Changes (`demo.sh` — `cmd_destroy`):**

- **Phase 0 (new):** Before running `terraform destroy`, pre-delete the JFrog project via `DELETE /access/api/v1/projects/{demo_name}?deleteRepos=true`. This atomically removes the build-info repo and the project, so the subsequent `project.demo` Terraform resource deletion becomes a no-op.
- Removed the earlier two-phase `-target` approach (it was superseded by this cleaner fix).
- After a successful destroy, delete the entire remote state folder (`/artifactory/{STATE_REPO}/{demo_name}/`) — not just the state file — so destroyed demos disappear from `./demo.sh list`.

---

## Files changed

| File | Change |
|------|--------|
| `demo/main.tf` | Add `local.curation_group_name`; add `platform_group.curation_waiver`; fix curation policy `decision_owners`; fix `xray_watch.block active = true` |
| `demo/variables.tf` | Change `curation_decision_owner_group` default to `""` |
| `demo/providers.tf` | Bump `required_version` to `>= 1.7` |
| `demo/tests/demo.tftest.hcl` | New location (moved from `tests/`); add `mock_provider` blocks |
| `base/main.tf` | Add `filter_criteria` to `platform_workers_service.sbom`; use `var.worker_action` |
| `base/variables.tf` | Add `worker_action` variable with validation |
| `base/providers.tf` | Bump `required_version` to `>= 1.7` |
| `base/tests/base.tftest.hcl` | New location (moved from `tests/`); add `mock_provider` blocks; fix action assertion |
| `demo.sh` | Fix storage API URL; fix curl auth username; fix grep pipefail; add `?deleteRepos=true` pre-delete; add state folder cleanup |
| `README.md` | Fix testing section; fix architecture tree; fix Terraform version; add missing variables; fix naming conventions |

---

## Task 2 – DRYRUN/BLOCK curation policy pairs with per-repo promotion

### Background

Audited the existing `SAGEN-*` curation policies on `psazuse` via `jf api /xray/api/v1/curation/policies`.
Seven policies were found, all `block` only:

| SAGEN policy name | Condition | condition_id | waiver | decision_owners |
|---|---|---|---|---|
| `SAGEN-CURATION_MALICIOUS_BLOCK` | Malicious package | 1 | forbidden | none |
| `SAGEN-CURATION_IMMATURE_BLOCK` | Package version is immature (permissive) | 14 | manual | `sagen-security-group` |
| `SAGEN_CURATION_AGED_BLOCK` | Package version is aged (no newer version) | 12 | manual | `sagen-security-group` |
| `SAGEN_CURATION_CRITICAL_BLOCK` | CVE CVSS ≥ 9 (with or without fix) | 3 | manual | `sagen-security-group` |
| `SAGEN_CURATION_NO_LIC_BLOCK` | Package has no identified license | 8 | manual | `sagen-security-group` |
| `SAGEN_CURATION_BLOCKED_LABEL_BLOCK` | Custom banned-label condition | 342 | forbidden | none |
| `SAGEN_CURATION_NO_DOCKERHUB_BLOCK` | Image is not Docker Hub official | 17 | manual | `sagen-security-group` |

The current demo module creates three block-only policies with ad-hoc names (`curation-malicious`, `curation-immature`, `curation-cvss-9`).
This task replaces them with six DRYRUN+BLOCK pairs following the agreed naming convention and adds a per-repo promotion mechanism.

### Goal

When `./demo.sh create <demo>` runs, create six curation policies:

| Policy name (with `demo_name` prefix) | Condition | Action | Waiver | Decision owners |
|---|---|---|---|---|
| `<demo>-CUR_MALICIOUS_DRYRUN` | Malicious package | `dry_run` | forbidden | none |
| `<demo>-CUR_MALICIOUS_BLOCK` | Malicious package | `block` | forbidden | none |
| `<demo>-CUR_OPR_IMMATURE_DRYRUN` | Package immature (permissive) | `dry_run` | forbidden | `<demo>-curation-waiver` |
| `<demo>-CUR_OPR_IMMATURE_BLOCK` | Package immature (permissive) | `block` | manual | `<demo>-curation-waiver` |
| `<demo>-CUR_OPR_AGED_DRYRUN` | Package aged (no newer version) | `dry_run` | forbidden | `<demo>-curation-waiver` |
| `<demo>-CUR_OPR_AGED_BLOCK` | Package aged (no newer version) | `block` | manual | `<demo>-curation-waiver` |

DRYRUN policies scope to **all** curated remote repos (audit mode for all).  
BLOCK policies scope to only the repos listed in the new `curation_block_repos` variable (enforcement mode per repo).  
Moving a repo from DRYRUN to BLOCK means adding it to `curation_block_repos` and re-running `./demo.sh create`.

### Design (DRY – `for_each` over a policy map)

#### 1. `demo/variables.tf` – new and updated variables

| Variable | Change | Default |
|---|---|---|
| `curation_aged_condition_id` | **New** – condition ID for "Package version is aged (no newer version)" | `"12"` |
| `curation_immature_condition_id` | Change default to permissive `"14"` (aligns with SAGEN) | `"14"` |
| `curation_malicious_condition_id` | No change; keep required (no default) | — |
| `curation_cvss_condition_id` | **Remove** – replaced by explicit BLOCK policies above | — |
| `curation_dryrun_repos` | **New** – list of remote repo keys to include in all DRYRUN policies; empty = all curated remotes | `[]` |
| `curation_block_repos` | **New** – list of remote repo keys to promote to BLOCK policies; subset of curated remotes | `[]` |

#### 2. `demo/locals.tf` (or locals block in `main.tf`) – policy map

```hcl
locals {
  curation_policy_map = var.enable_curation ? {
    "CUR_MALICIOUS_DRYRUN"    = { condition_id = var.curation_malicious_condition_id, action = "dry_run", waiver = "forbidden", owners = [] }
    "CUR_MALICIOUS_BLOCK"     = { condition_id = var.curation_malicious_condition_id, action = "block",   waiver = "forbidden", owners = [] }
    "CUR_OPR_IMMATURE_DRYRUN" = { condition_id = var.curation_immature_condition_id,  action = "dry_run", waiver = "forbidden", owners = [local.curation_group_name] }
    "CUR_OPR_IMMATURE_BLOCK"  = { condition_id = var.curation_immature_condition_id,  action = "block",   waiver = "manual",   owners = [local.curation_group_name] }
    "CUR_OPR_AGED_DRYRUN"     = { condition_id = var.curation_aged_condition_id,       action = "dry_run", waiver = "forbidden", owners = [local.curation_group_name] }
    "CUR_OPR_AGED_BLOCK"      = { condition_id = var.curation_aged_condition_id,       action = "block",   waiver = "manual",   owners = [local.curation_group_name] }
  } : {}
}
```

#### 3. `demo/main.tf` – single `for_each` resource replaces three `count` resources

```hcl
resource "xray_curation_policy" "demo" {
  for_each = local.curation_policy_map

  name                  = "${var.demo_name}-${each.key}"
  condition_id          = each.value.condition_id
  scope                 = "specific_repos"
  policy_action         = each.value.action
  waiver_request_config = each.value.waiver
  decision_owners       = each.value.owners != [] ? each.value.owners : null

  depends_on = [platform_group.curation_waiver, /* all remote repos */]
}
```

`repo_include` is still injected via the override file (provider ValidateConfig limitation – see Task 1 notes).

#### 4. `demo.sh` – `generate_curation_override()` function

Currently generates override entries for `malicious`, `immature`, `cvss`.  
**Replace** with entries for all six keys using the new `for_each` resource address pattern:

- `xray_curation_policy.demo["CUR_MALICIOUS_DRYRUN"]` → `repo_include` = all curated remote repo keys
- `xray_curation_policy.demo["CUR_MALICIOUS_BLOCK"]` → `repo_include` = `curation_block_repos` variable value
- Same pattern for IMMATURE and AGED pairs.

`curation_block_repos` must be passed into the override generator (read from `terraform.tfvars` or a separate `--block-repos` flag).

#### 5. `demos/acme.tfvars` – default wiring

```hcl
curation_malicious_condition_id = "1"   # Malicious package (platform-wide)
curation_immature_condition_id  = "14"  # Immature permissive (matches SAGEN)
curation_aged_condition_id      = "12"  # Aged – no newer version (matches SAGEN)
curation_block_repos            = []    # Start all repos in DRYRUN; add keys here to promote
```

#### 6. Promotion workflow

To move `acme-npm-remote` from DRYRUN to BLOCK enforcement:

```hcl
# demos/acme.tfvars
curation_block_repos = ["acme-npm-remote"]
```

Then run:

```bash
./demo.sh create acme   # re-applies; adds the repo to BLOCK policies
```

To revert, remove the repo key and run `create` again.

### Files to change

| File | Change |
|---|---|
| `demo/variables.tf` | Add `curation_aged_condition_id`, `curation_dryrun_repos`, `curation_block_repos`; update `curation_immature_condition_id` default; remove `curation_cvss_condition_id` |
| `demo/main.tf` | Replace `xray_curation_policy.malicious/immature/cvss` with single `xray_curation_policy.demo` using `for_each` over `local.curation_policy_map` |
| `demo/locals.tf` | Add `curation_policy_map` local (or inline in `main.tf`) |
| `demo/tests/demo.tftest.hcl` | Update assertions for new resource address pattern (`xray_curation_policy.demo["CUR_MALICIOUS_BLOCK"]` etc.) |
| `demo.sh` | Update `generate_curation_override()` for the six new policy keys and repo-tier split |
| `demos/acme.tfvars` | Add new condition ID variables; add empty `curation_block_repos = []` |
| `demos/_base.tfvars` | Add new condition ID defaults where applicable |
| `README.md` | Document new variables and promotion workflow |

---

## Task 3 – Add remaining 4 SAGEN-equivalent curation policy pairs

### Background

Task 2 implemented DRYRUN/BLOCK pairs for 3 of the 7 SAGEN reference policies.
The remaining 4 were not in the original request but are now needed for full coverage:

| SAGEN policy | Condition | condition_id | waiver | decision_owners |
|---|---|---|---|---|
| `SAGEN_CURATION_CRITICAL_BLOCK` | CVE CVSS ≥ 9 (with or without fix) | 3 | manual | `sagen-security-group` |
| `SAGEN_CURATION_NO_LIC_BLOCK` | Package has no identified license | 8 | manual | `sagen-security-group` |
| `SAGEN_CURATION_BLOCKED_LABEL_BLOCK` | Custom banned-label condition | 342 (custom) | forbidden | none |
| `SAGEN_CURATION_NO_DOCKERHUB_BLOCK` | Image is not Docker Hub official | 17 | manual | `sagen-security-group` |

### New policy pairs

| Policy name | Condition | Tier | waiver | decision_owners |
|---|---|---|---|---|
| `<demo>-CUR_CVE_CRITICAL_DRYRUN` | CVE CVSS ≥ 9 | dry_run | forbidden | none |
| `<demo>-CUR_CVE_CRITICAL_BLOCK` | CVE CVSS ≥ 9 | block | manual | curation-waiver group |
| `<demo>-CUR_NO_LICENSE_DRYRUN` | No identified license | dry_run | forbidden | none |
| `<demo>-CUR_NO_LICENSE_BLOCK` | No identified license | block | manual | curation-waiver group |
| `<demo>-CUR_NO_DOCKERHUB_DRYRUN` | Not Docker Hub official | dry_run | forbidden | none |
| `<demo>-CUR_NO_DOCKERHUB_BLOCK` | Not Docker Hub official | block | manual | curation-waiver group |
| `<demo>-CUR_BANNED_LABEL_DRYRUN` *(optional)* | Custom banned-label | dry_run | forbidden | none |
| `<demo>-CUR_BANNED_LABEL_BLOCK` *(optional)* | Custom banned-label | block | forbidden | none |

`CUR_BANNED_LABEL` is **optional**: created only when `curation_banned_label_condition_id` is set (non-empty).
The banned-label condition ID is org-specific (342 on psazuse) and not portable.

### Design (extends Task 2 – no structural changes)

The `curation_conditions` local (introduced in Task 2) is expanded using `merge()`:

```hcl
curation_conditions = merge(
  {
    # -- existing --
    "CUR_MALICIOUS"    = { condition_id = var.curation_malicious_condition_id,  waiver = "forbidden", owners = [] }
    "CUR_OPR_IMMATURE" = { condition_id = var.curation_immature_condition_id,   waiver = "manual",   owners = [local.curation_group_name] }
    "CUR_OPR_AGED"     = { condition_id = var.curation_aged_condition_id,        waiver = "manual",   owners = [local.curation_group_name] }
    # -- new --
    "CUR_CVE_CRITICAL" = { condition_id = var.curation_critical_condition_id,    waiver = "manual",   owners = [local.curation_group_name] }
    "CUR_NO_LICENSE"   = { condition_id = var.curation_no_license_condition_id,  waiver = "manual",   owners = [local.curation_group_name] }
    "CUR_NO_DOCKERHUB" = { condition_id = var.curation_no_dockerhub_condition_id,waiver = "manual",   owners = [local.curation_group_name] }
  },
  var.curation_banned_label_condition_id != "" ? {
    "CUR_BANNED_LABEL" = { condition_id = var.curation_banned_label_condition_id, waiver = "forbidden", owners = [] }
  } : {}
)
```

The `xray_curation_policy.dryrun` and `xray_curation_policy.block` `for_each` resources
(Task 2) automatically pick up the expanded map — no resource-level changes needed.

### Files to change

| File | Change |
|---|---|
| `demo/variables.tf` | Add `curation_critical_condition_id` (default `"3"`), `curation_no_license_condition_id` (default `"8"`), `curation_no_dockerhub_condition_id` (default `"17"`), `curation_banned_label_condition_id` (default `""`) |
| `demo/main.tf` | Expand `curation_conditions` local with the 4 new entries via `merge()` |
| `demo/tests/demo.tftest.hcl` | Add variable values for new condition IDs + assertions for `CUR_CVE_CRITICAL`, `CUR_NO_LICENSE`, `CUR_NO_DOCKERHUB` |
| `demos/acme.tfvars` | Add new condition ID variables with platform defaults |
| `README.md` | Update policy table (10 policies) and promotion section |
