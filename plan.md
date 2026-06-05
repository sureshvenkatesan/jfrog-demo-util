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
