#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="${SCRIPT_DIR}/base"
DEMO_DIR="${SCRIPT_DIR}/demo"
BOOTSTRAP_DIR="${SCRIPT_DIR}/bootstrap"
DEMOS_DIR="${SCRIPT_DIR}/demos"
BASE_TFVARS="${DEMOS_DIR}/_base.tfvars"

STATE_REPO="${TF_STATE_REPO:-demo-util-tfstate}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [args]

Commands:
  bootstrap                Create the remote state backend repository (one-time setup).
  create  <demo-name>      Spin up a new demo environment.
  destroy <demo-name>      Tear down a demo environment.
  plan    <demo-name>      Show what would change for a demo.
  status  <demo-name>      Show current state of a demo.
  output  <demo-name>      Show Terraform outputs for a demo.
  list                     List active demos.

Curation condition helpers:
  list-curation-conditions               List all custom curation conditions on the platform.
  list-catalog-labels [filter]           List custom catalog labels (optional substring filter, e.g. "acme").
  create-curation-condition [name] [label]  Create a BannedLabels curation condition.
                                            [name]   Condition name (default: demo-banned-label).
                                            [label]  Catalog label to use (default: <name> minus -label suffix,
                                                     e.g. "acme-banned-label" → "acme-banned").
                                                     Label is created via Catalog GraphQL API if it doesn't exist.
                                            Prints the condition ID to set in curation_banned_label_condition_id.

Optional (worker + webhook):
  init-base                Apply shared base resources. Requires enable_worker_webhook = true in _base.tfvars.
  destroy-base             Destroy shared base resources.

The script expects:
  - ${DEMOS_DIR}/_base.tfvars          (shared credentials: jfrog_url, jfrog_access_token)
  - ${DEMOS_DIR}/<demo-name>.tfvars    (per-demo: demo_name, repos, curation, etc.)

Credentials can also be provided via environment variables:
  TF_VAR_jfrog_url, TF_VAR_jfrog_access_token

Remote state is stored in Artifactory repo "${STATE_REPO}".
Override via TF_STATE_REPO env var if using a different repo name.
Run "$(basename "$0") bootstrap" once before the first demo to create the repo.
EOF
  exit 1
}

# ---------------------------------------------------------------------------
# Credential helpers
# ---------------------------------------------------------------------------

parse_jfrog_creds() {
  if [[ -f "${BASE_TFVARS}" ]]; then
    JFROG_URL=$(grep -E '^\s*jfrog_url\s*=' "${BASE_TFVARS}" | head -1 \
      | sed 's/.*= *"\([^"]*\)".*/\1/')
    JFROG_TOKEN=$(grep -E '^\s*jfrog_access_token\s*=' "${BASE_TFVARS}" | head -1 \
      | sed 's/.*= *"\([^"]*\)".*/\1/')
  fi
  JFROG_URL="${JFROG_URL:-${TF_VAR_jfrog_url:-}}"
  JFROG_TOKEN="${JFROG_TOKEN:-${TF_VAR_jfrog_access_token:-}}"

  if [[ -z "${JFROG_URL}" || -z "${JFROG_TOKEN}" ]]; then
    echo "Error: jfrog_url and jfrog_access_token must be set (via _base.tfvars or TF_VAR_ env vars)."
    exit 1
  fi

  # Extract the JFrog username from the JWT access token's "sub" claim
  # (e.g. "jfac@.../users/chaitanyag" → "chaitanyag"). Artifactory's
  # Terraform Backend API requires the real username for Basic Auth.
  local jfrog_user
  jfrog_user=$(python3 -c "
import base64, json, sys
p = sys.argv[1].split('.')[1]
p += '=' * (4 - len(p) % 4)
d = json.loads(base64.urlsafe_b64decode(p))
print(d.get('sub', '').rsplit('/users/', 1)[-1])
" "${JFROG_TOKEN}" 2>/dev/null) || jfrog_user=""

  if [[ -z "${jfrog_user}" ]]; then
    echo "Error: could not extract username from JFrog access token." >&2
    exit 1
  fi

  # Terraform's HTTP backend uses Basic Auth; the access token is passed as the
  # password and the username must be the real JFrog user (not a placeholder).
  export TF_HTTP_USERNAME="${jfrog_user}"
  export TF_HTTP_PASSWORD="${JFROG_TOKEN}"
  export TF_VAR_jfrog_username="${jfrog_user}"
}

base_var_file_args() {
  if [[ -f "${BASE_TFVARS}" ]]; then
    echo "-var-file=${BASE_TFVARS}"
  fi
}

ensure_base_tfvars() {
  if [[ ! -f "${BASE_TFVARS}" ]]; then
    echo "Error: ${BASE_TFVARS} not found."
    echo "Copy demos/_base.tfvars.example to demos/_base.tfvars and fill in your values."
    exit 1
  fi
}

ensure_demo_tfvars() {
  local name="$1"
  local tfvars="${DEMOS_DIR}/${name}.tfvars"
  if [[ ! -f "${tfvars}" ]]; then
    echo "Error: ${tfvars} not found."
    echo "Create it first. See demos/acme.tfvars.example for reference."
    exit 1
  fi
}

# Read a single quoted string value from a tfvars file.
# Usage: read_tfvar <key> <tfvars-file>
read_tfvar() {
  local key="$1" file="$2"
  grep -E "^\s*${key}\s*=" "${file}" | head -1 \
    | sed 's/.*= *"\([^"]*\)".*/\1/' || true
}

# Read enable_project from a tfvars file; defaults to "true" when absent.
# Usage: read_enable_project <tfvars-file>
read_enable_project() {
  local val
  val=$(grep -E '^\s*enable_project\s*=' "${1}" | head -1 \
    | sed 's/.*=\s*//' | tr -d ' "' || true)
  echo "${val:-true}"
}

# ---------------------------------------------------------------------------
# JFrog API helpers  (require parse_jfrog_creds to have been called)
# ---------------------------------------------------------------------------

# GET a JFrog API path; prints response body. Returns curl exit code.
# Usage: jfrog_get <path>
jfrog_get() {
  curl -sf -H "Authorization: Bearer ${JFROG_TOKEN}" \
    "${JFROG_URL}${1}" 2>/dev/null
}

# POST JSON to a JFrog API path; prints response body.
# Usage: jfrog_post <path> <json-body>
jfrog_post() {
  curl -sf -X POST \
    -H "Authorization: Bearer ${JFROG_TOKEN}" \
    -H "Content-Type: application/json" \
    "${JFROG_URL}${1}" \
    -d "${2}" 2>/dev/null
}

# Call a JFrog API and return only the HTTP status code (body discarded).
# Usage: jfrog_http_status <METHOD> <path> [extra-curl-args...]
jfrog_http_status() {
  local method="$1" path="$2"; shift 2
  curl -s -o /dev/null -w "%{http_code}" \
    -X "${method}" \
    -H "Authorization: Bearer ${JFROG_TOKEN}" \
    "${JFROG_URL}${path}" \
    "$@" 2>/dev/null
}

# POST a GraphQL query to the JFrog Catalog custom GraphQL API.
# Usage: jfrog_catalog_graphql <query-string>
jfrog_catalog_graphql() {
  local query="$1"
  local payload=/tmp/catalog_gql_$$.json
  printf '%s' "${query}" > "${payload}"
  local resp
  resp=$(curl -sf -X POST \
    -H "Authorization: Bearer ${JFROG_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary @"${payload}" \
    "${JFROG_URL}/catalog/api/v1/custom/graphql" 2>/dev/null) || resp=""
  rm -f "${payload}"
  echo "${resp}"
}

# ---------------------------------------------------------------------------
# Remote backend initialisation (Artifactory Terraform Backend repo)
#
# URL pattern:
#   https://<instance>/artifactory/api/terraform/state/<repo-key>/<state-name>
# ---------------------------------------------------------------------------

# init_terraform <chdir-dir> <state-name>
init_terraform() {
  local chdir="$1" state_name="$2"
  local state_url="${JFROG_URL}/artifactory/${STATE_REPO}/${state_name}/terraform.tfstate"
  local init_log
  init_log=$(mktemp)

  if ! terraform -chdir="${chdir}" init -reconfigure \
    -backend-config="address=${state_url}" \
    -backend-config="update_method=PUT" \
    > "${init_log}" 2>&1; then
    echo "Error: terraform init failed for '${state_name}':" >&2
    cat "${init_log}" >&2
    rm -f "${init_log}"
    exit 1
  fi
  rm -f "${init_log}"
}

init_demo()  { init_terraform "${DEMO_DIR}"  "$1"; }
init_base()  { init_terraform "${BASE_DIR}"  "base"; }

# ---------------------------------------------------------------------------
# Bootstrap (one-time) – create the Terraform Backend repository
# ---------------------------------------------------------------------------

cmd_bootstrap() {
  parse_jfrog_creds

  echo "==> Bootstrapping remote state repository '${STATE_REPO}'..."
  terraform -chdir="${BOOTSTRAP_DIR}" init > /dev/null 2>&1
  terraform -chdir="${BOOTSTRAP_DIR}" apply \
    -var="jfrog_url=${JFROG_URL}" \
    -var="jfrog_access_token=${JFROG_TOKEN}" \
    -var="state_repo_key=${STATE_REPO}" \
    "$@"

  echo ""
  echo "Backend repository '${STATE_REPO}' is ready."
}

# ---------------------------------------------------------------------------
# Base lifecycle (optional -- worker + webhook)
# ---------------------------------------------------------------------------

cmd_init_base() {
  ensure_base_tfvars
  parse_jfrog_creds

  echo "==> Initializing base module..."
  init_base

  echo "==> Applying base resources..."
  terraform -chdir="${BASE_DIR}" apply \
    -var-file="${BASE_TFVARS}" \
    "$@"

  echo ""
  echo "Base resources applied."
}

cmd_destroy_base() {
  ensure_base_tfvars
  parse_jfrog_creds

  local active
  active=$(cmd_list_quiet)
  if [[ -n "${active}" ]]; then
    echo "Error: active demos still exist. Destroy them first:"
    echo "${active}"
    exit 1
  fi

  init_base

  echo "==> Destroying base resources..."
  terraform -chdir="${BASE_DIR}" destroy \
    -var-file="${BASE_TFVARS}" \
    "$@"

  echo "Base resources destroyed."
}

# ---------------------------------------------------------------------------
# Curation override generator
#
# The xray provider's ValidateConfig rejects any non-literal value for
# repo_include (variables, locals, for-expressions are all unknown at that
# phase). We work around this by generating a Terraform override file with
# literal repo key values before each command.
# ---------------------------------------------------------------------------

generate_curation_override() {
  local name="$1"
  local tfvars="${DEMOS_DIR}/${name}.tfvars"
  local out="${DEMO_DIR}/curation_override.tf.json"

  local demo_name
  demo_name=$(read_tfvar "demo_name" "${tfvars}")

  # Collect all remote repo keys whose package_type is supported by JFrog Curation.
  # These are the repos placed into DRYRUN (audit-only) policies.
  local all_keys=()
  while IFS= read -r suffix; do
    [[ -n "${suffix}" ]] && all_keys+=("\"${demo_name}-${suffix}\"")
  done < <(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
supported = {'npm', 'pypi', 'maven', 'gradle', 'go', 'nuget', 'docker'}
for m in re.finditer(
    r'\"([^\"]*-remote)\"\s*=\s*\{[^}]*package_type\s*=\s*\"(\w+)\"',
    content, re.DOTALL,
):
    key, pkg = m.groups()
    if pkg in supported:
        print(key)
" "${tfvars}")

  if [[ ${#all_keys[@]} -eq 0 ]]; then
    rm -f "${out}"
    return
  fi

  # Collect repos promoted to BLOCK enforcement (curation_block_repos variable).
  # When the list is empty, BLOCK policies use scope="all" and need no repo_include.
  local block_keys=()
  while IFS= read -r key; do
    [[ -n "${key}" ]] && block_keys+=("\"${key}\"")
  done < <(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
m = re.search(r'curation_block_repos\s*=\s*\[([^\]]*)\]', content, re.DOTALL)
if m:
    for item in re.findall(r'\"([^\"]+)\"', m.group(1)):
        print(item)
" "${tfvars}")

  local dryrun_array
  dryrun_array=$(IFS=,; echo "${all_keys[*]}")

  # Build the override JSON. The xray provider's ValidateConfig requires
  # repo_include to be a literal list at plan time (no variables/locals).
  # DRYRUN: all curated remote repos (audit-only visibility).
  # BLOCK:  only repos promoted via curation_block_repos; omitted when empty
  #         so the resource falls back to scope="all" set in main.tf.
  if [[ ${#block_keys[@]} -gt 0 ]]; then
    local block_array
    block_array=$(IFS=,; echo "${block_keys[*]}")
    cat > "${out}" <<EOFJ
{
  "resource": {
    "xray_curation_policy": {
      "dryrun": { "repo_include": [${dryrun_array}] },
      "block":  { "repo_include": [${block_array}] }
    }
  }
}
EOFJ
  else
    cat > "${out}" <<EOFJ
{
  "resource": {
    "xray_curation_policy": {
      "dryrun": { "repo_include": [${dryrun_array}] }
    }
  }
}
EOFJ
  fi
}

# Shared setup for all demo lifecycle commands: init backend + generate override.
setup_demo() {
  local name="$1"
  init_demo "${name}"
  generate_curation_override "${name}"
}

# ---------------------------------------------------------------------------
# Catalog label + curation condition helpers (shared)
# ---------------------------------------------------------------------------

# Ensure a catalog label exists, creating it via GraphQL if needed (idempotent).
# Usage: ensure_catalog_label <label_name>
ensure_catalog_label() {
  local label_name="$1"
  local resp
  resp=$(jfrog_catalog_graphql \
    "{\"query\":\"mutation { customCatalogLabel { createCustomCatalogLabel(label: { name: \\\"${label_name}\\\", description: \\\"Demo banned label for Curation policy demo\\\" }) { name } } }\"}")

  local err
  err=$(echo "${resp}" | python3 -c "
import json, sys
r = json.load(sys.stdin)
errs = r.get('errors', [])
msgs = [e.get('message','') for e in errs if 'already exist' not in e.get('message','')]
print(msgs[0] if msgs else '')
" 2>/dev/null || true)

  if [[ -n "${err}" ]]; then
    echo "  Warning: catalog label creation returned: ${err}" >&2
  else
    echo "  Catalog label '${label_name}' ready."
  fi
}

# Find an existing curation condition by name whose label matches expected_label.
# Prints the condition ID when both name and label match; empty otherwise.
# Usage: find_curation_condition <condition_name> <expected_label>
find_curation_condition() {
  local condition_name="$1" expected_label="$2"
  jfrog_get "/xray/api/v1/curation/conditions" \
    | python3 -c "
import json, sys
condition_name, expected_label = sys.argv[1], sys.argv[2]
r = json.load(sys.stdin)
conditions = r.get('data', r) if isinstance(r, dict) else r
for c in conditions:
    if c.get('name') != condition_name:
        continue
    labels = []
    for p in c.get('param_values', []):
        v = p.get('value')
        if isinstance(v, list):
            labels.extend(v)
    if expected_label in labels:
        print(c.get('id', ''))
    else:
        print(f'LABEL_MISMATCH:{c.get(\"id\",\"\")}:{\"|\".join(labels)}', file=sys.stderr)
    break
" "${condition_name}" "${expected_label}" 2>/tmp/find_condition_$$.err || true
  cat /tmp/find_condition_$$.err >&2 2>/dev/null || true
  rm -f /tmp/find_condition_$$.err
}

# Create a BannedLabels curation condition; prints the assigned ID.
# Usage: create_curation_condition <condition_name> <label_name>
create_curation_condition() {
  local condition_name="$1" label_name="$2"
  local resp
  resp=$(jfrog_post "/xray/api/v1/curation/conditions" \
    "{\"name\":\"${condition_name}\",\"risk_type\":\"security\",\"condition_template_id\":\"BannedLabels\",\"param_values\":[{\"param_id\":\"list_of_labels\",\"value\":[\"${label_name}\"]}]}") || resp=""

  echo "${resp}" | python3 -c "
import json, sys
r = json.load(sys.stdin)
obj = r.get('data', r) if isinstance(r, dict) and 'data' in r else r
print(obj.get('id', '') if isinstance(obj, dict) else '')
" 2>/dev/null || true
}

# Delete a curation condition by name (looks up the ID first).
# No-ops silently when the condition does not exist.
# Usage: delete_curation_condition <condition_name>
delete_curation_condition() {
  local condition_name="$1"
  local cond_id
  cond_id=$(jfrog_get "/xray/api/v1/curation/conditions" \
    | python3 -c "
import json, sys
r = json.load(sys.stdin)
conditions = r.get('data', r) if isinstance(r, dict) else r
for c in conditions:
    if c.get('name') == sys.argv[1]:
        print(c.get('id', ''))
        break
" "${condition_name}" 2>/dev/null || true)

  if [[ -z "${cond_id}" ]]; then
    echo "  Curation condition '${condition_name}' not found — skipping."
    return
  fi

  local http_status
  http_status=$(jfrog_http_status DELETE "/xray/api/v1/curation/conditions/${cond_id}")
  if [[ "${http_status}" == "20"* ]]; then
    echo "  Curation condition '${condition_name}' (ID ${cond_id}) deleted."
  else
    echo "  Warning: could not delete condition '${condition_name}' (ID ${cond_id}) — HTTP ${http_status}." >&2
    echo "           It may still be in use by a policy. Delete it manually via Administration → Curation → Conditions." >&2
  fi
}

# Delete a catalog label by name via GraphQL.
# Correct mutation: deleteCustomCatalogLabel(label: { name: "..." })
# No-ops silently when the label does not exist.
# Usage: delete_catalog_label <label_name>
delete_catalog_label() {
  local label_name="$1"
  local resp
  resp=$(jfrog_catalog_graphql \
    "{\"query\":\"mutation { customCatalogLabel { deleteCustomCatalogLabel(label: { name: \\\"${label_name}\\\" }) } }\"}")

  local err
  err=$(echo "${resp}" | python3 -c "
import json, sys
r = json.load(sys.stdin)
errs = r.get('errors', [])
msgs = [e.get('message','') for e in errs if 'not found' not in e.get('message','').lower() and 'does not exist' not in e.get('message','').lower()]
print(msgs[0] if msgs else '')
" 2>/dev/null || true)

  if [[ -n "${err}" ]]; then
    echo "  Warning: could not delete catalog label '${label_name}': ${err}" >&2
  else
    echo "  Catalog label '${label_name}' deleted (or did not exist)."
  fi
}

# ---------------------------------------------------------------------------
# Demo lifecycle
# ---------------------------------------------------------------------------

cmd_create() {
  local name="${1:?demo name required}"
  ensure_demo_tfvars "${name}"
  parse_jfrog_creds

  local tfvars="${DEMOS_DIR}/${name}.tfvars"
  local demo_name
  demo_name=$(read_tfvar "demo_name" "${tfvars}")

  # Auto-provision the CUR_BANNED_LABEL curation condition when the tfvars
  # entry is absent or commented out. The condition is idempotent: reuses an
  # existing one by name or creates it. The resolved ID is written back into
  # the tfvars so all 14 curation policies are created.
  local banned_id
  banned_id=$(read_tfvar "curation_banned_label_condition_id" "${tfvars}")

  if [[ -z "${banned_id}" ]]; then
    local condition_name="${demo_name}-banned-label"
    local banned_label="${demo_name}-banned"
    echo "==> CUR_BANNED_LABEL not set – provisioning condition '${condition_name}'..."

    ensure_catalog_label "${banned_label}"

    # find_curation_condition only returns an ID when the condition exists AND
    # uses the expected label. A name match with a wrong label emits a warning
    # on stderr so the user knows a stale condition exists with a different label.
    banned_id=$(find_curation_condition "${condition_name}" "${banned_label}" 2>/tmp/fc_warn_$$.txt)
    local fc_warn
    fc_warn=$(cat /tmp/fc_warn_$$.txt 2>/dev/null || true)
    rm -f /tmp/fc_warn_$$.txt

    if [[ "${fc_warn}" == LABEL_MISMATCH:* ]]; then
      local old_id old_labels
      old_id=$(echo "${fc_warn}" | cut -d: -f2)
      old_labels=$(echo "${fc_warn}" | cut -d: -f3)
      echo "  Warning: condition '${condition_name}' (ID ${old_id}) exists but uses label(s) '${old_labels}'" >&2
      echo "           not '${banned_label}'. Delete it first to auto-create with the correct label." >&2
      echo "           Reusing condition ID ${old_id} as-is." >&2
      banned_id="${old_id}"
    elif [[ -n "${banned_id}" ]]; then
      echo "  Found existing condition '${condition_name}' with label '${banned_label}' — ID: ${banned_id}."
    else
      echo "  Creating BannedLabels condition '${condition_name}' (label: ${banned_label})..."
      banned_id=$(create_curation_condition "${condition_name}" "${banned_label}")
    fi

    if [[ -n "${banned_id}" ]]; then
      if grep -qE '^\s*#.*curation_banned_label_condition_id' "${tfvars}"; then
        sed -i '' \
          "s|^.*curation_banned_label_condition_id.*$|curation_banned_label_condition_id = \"${banned_id}\"|" \
          "${tfvars}"
      else
        printf '\ncuration_banned_label_condition_id = "%s"\n' "${banned_id}" >> "${tfvars}"
      fi
      echo "  Wrote curation_banned_label_condition_id = \"${banned_id}\" to ${name}.tfvars."
    else
      echo "  Warning: could not resolve CUR_BANNED_LABEL condition – creating 12 policies instead of 14." >&2
    fi
  fi

  echo "==> Initializing demo module for '${name}'..."
  setup_demo "${name}"

  # When enable_project = true: if the project already exists (orphaned from a
  # previous destroy), import it so apply can update rather than fail.
  local enable_project
  enable_project=$(read_enable_project "${tfvars}")
  if [[ "${enable_project}" == "true" ]]; then
    local proj_http
    proj_http=$(jfrog_http_status GET "/access/api/v1/projects/${demo_name}")
    if [[ "${proj_http}" == "20"* ]]; then
      local in_state
      in_state=$(terraform -chdir="${DEMO_DIR}" state list 2>/dev/null | grep -c '^project\.demo\[0\]$' || true)
      if [[ "${in_state}" -eq 0 ]]; then
        echo "  Project '${demo_name}' exists but is not in Terraform state — importing..."
        terraform -chdir="${DEMO_DIR}" import \
          $(base_var_file_args) \
          -var-file="${tfvars}" \
          'project.demo[0]' "${demo_name}" > /dev/null 2>&1 || true
      fi
    fi
  fi

  echo "==> Applying demo '${name}'..."
  terraform -chdir="${DEMO_DIR}" apply \
    $(base_var_file_args) \
    -var-file="${tfvars}" \
    "${@:2}"

  echo ""
  echo "Demo '${name}' is ready."
  terraform -chdir="${DEMO_DIR}" output
}

cmd_destroy() {
  local name="${1:?demo name required}"
  ensure_demo_tfvars "${name}"
  parse_jfrog_creds

  setup_demo "${name}"

  local tfvars="${DEMOS_DIR}/${name}.tfvars"
  local demo_name
  demo_name=$(read_tfvar "demo_name" "${tfvars}")

  local enable_project
  enable_project=$(read_enable_project "${tfvars}")

  if [[ "${enable_project}" == "true" ]]; then
    # Drop the project resource from Terraform state so that `terraform destroy`
    # can complete cleanly. Terraform would otherwise try to delete the project
    # while JFrog's auto-created <demo_name>-build-info repo is still attached,
    # which the Access API rejects (HTTP 400: "Project containing resources can't
    # be removed"). We attempt the real API project delete below, after all other
    # resources have been torn down.
    echo "==> Pre-cleanup: removing project.demo[0] from Terraform state..."
    terraform -chdir="${DEMO_DIR}" state rm 'project.demo[0]' > /dev/null 2>&1 || true
  fi

  echo "==> Destroying demo '${name}' Terraform resources..."
  terraform -chdir="${DEMO_DIR}" destroy \
    $(base_var_file_args) \
    -var-file="${tfvars}" \
    "${@:2}"

  # Clean up out-of-band resources created by cmd_create (not tracked by Terraform).
  # Done here regardless of project deletion outcome so they are never left orphaned.
  local condition_name="${demo_name}-banned-label"
  local banned_label="${demo_name}-banned"
  echo "==> Cleaning up BannedLabels condition '${condition_name}'..."
  delete_curation_condition "${condition_name}"
  echo "==> Cleaning up catalog label '${banned_label}'..."
  delete_catalog_label "${banned_label}"

  # Comment out the condition ID in tfvars so the next create auto-provisions it.
  if grep -qE '^\s*curation_banned_label_condition_id\s*=' "${tfvars}" 2>/dev/null; then
    sed -i '' \
      's|^\(.*curation_banned_label_condition_id.*\)$|# \1|' \
      "${tfvars}"
    echo "  Commented out curation_banned_label_condition_id in ${name}.tfvars."
  fi

  # Attempt to delete the JFrog project via the Access API now that all managed
  # repos and policies have been removed. On JFrog SaaS the build-info repo
  # persists for ~15 minutes after resource deletion before the platform
  # garbage-collects it, so the first attempt may return HTTP 400.
  if [[ "${enable_project}" == "true" ]]; then
    echo "==> Attempting to delete JFrog project '${demo_name}'..."
    local proj_http
    proj_http=$(jfrog_http_status DELETE "/access/api/v1/projects/${demo_name}")
    if [[ "${proj_http}" == "20"* || "${proj_http}" == "404" ]]; then
      echo "  Project '${demo_name}' deleted."
    else
      echo ""
      echo "WARNING: Could not delete JFrog project '${demo_name}' (HTTP ${proj_http})."
      echo "  On JFrog SaaS instances the auto-created build-info repository can take"
      echo "  up to 15 minutes to be garbage-collected before the project can be removed."
      echo ""
      echo "  Options:"
      echo "    1. Wait ~15 minutes, then re-run:"
      echo "         ./$(basename "$0") destroy ${name} -auto-approve"
      echo "       Terraform will find nothing to destroy and only the project delete"
      echo "       will be retried."
      echo ""
      echo "    2. Delete the project immediately from the JFrog UI:"
      echo "         Administration → Projects → ⋮ → Delete"
      echo "       Then remove the orphaned Terraform state entry:"
      echo "         terraform -chdir=demo state rm 'project.demo[0]'"
      echo ""
      echo "All other demo resources (repos, policies, watches, condition, label) have"
      echo "been destroyed. Only the project and its build-info repo remain."
      exit 1
    fi
  fi

  # Remove the entire remote state folder so this demo no longer appears in
  # `list`. Only reached when all cleanup (including project deletion) succeeded.
  # Deleting the folder (not just the .tfstate file) avoids the Artifactory
  # empty-folder ghost that the storage listing still returns.
  local state_folder="${JFROG_URL}/artifactory/${STATE_REPO}/${demo_name}/"
  curl -sf -X DELETE -u "${TF_HTTP_USERNAME}:${JFROG_TOKEN}" "${state_folder}" 2>/dev/null \
    && echo "Remote state for '${demo_name}' removed." \
    || echo "Warning: could not remove remote state at ${state_folder}."

  echo "Demo '${name}' destroyed."
}

cmd_plan() {
  local name="${1:?demo name required}"
  ensure_demo_tfvars "${name}"
  parse_jfrog_creds

  setup_demo "${name}"
  terraform -chdir="${DEMO_DIR}" plan \
    $(base_var_file_args) \
    -var-file="${DEMOS_DIR}/${name}.tfvars" \
    "${@:2}"
}

cmd_status() {
  local name="${1:?demo name required}"
  parse_jfrog_creds

  setup_demo "${name}"
  terraform -chdir="${DEMO_DIR}" show
}

cmd_output() {
  local name="${1:?demo name required}"
  parse_jfrog_creds

  setup_demo "${name}"
  terraform -chdir="${DEMO_DIR}" output
}

# List demos by querying the Artifactory storage API for the backend repo.
cmd_list_quiet() {
  parse_jfrog_creds

  local api_url="${JFROG_URL}/artifactory/api/storage/${STATE_REPO}/"
  local response
  response=$(curl -sf -u "${TF_HTTP_USERNAME}:${JFROG_TOKEN}" "${api_url}" 2>/dev/null) || return 0

  local uris
  uris=$(echo "${response}" | grep -oE '"uri" *: *"/[^"]*"' || true)
  [[ -z "${uris}" ]] && return 0
  echo "${uris}" | sed 's|.*"/\([^"]*\)"|\1|' | grep -v '^base$' || true
}

cmd_list() {
  local demos
  demos=$(cmd_list_quiet)
  if [[ -z "${demos}" ]]; then
    echo "No active demos."
  else
    echo "Active demos:"
    echo "${demos}" | while read -r name; do
      echo "  - ${name}"
    done
  fi
}

# ---------------------------------------------------------------------------
# Curation condition helpers
# ---------------------------------------------------------------------------

# List all custom curation conditions on the platform.
cmd_list_curation_conditions() {
  parse_jfrog_creds

  echo "==> Fetching custom curation conditions from ${JFROG_URL}..."
  local response
  response=$(jfrog_get "/xray/api/v1/curation/conditions")

  echo "${response}" | python3 -c "
import json, sys
r = json.load(sys.stdin)
conditions = r.get('data', r) if isinstance(r, dict) else r
custom = [c for c in conditions if c.get('is_custom')]
if not custom:
    print('No custom conditions found.')
    sys.exit(0)
print(f'{'ID':<6}  {'Template':<20}  {'Name'}')
print('-' * 60)
for c in sorted(custom, key=lambda x: int(x.get('id', 0))):
    params = ', '.join(
        str(p.get('value', '')) for p in c.get('param_values', [])
    )
    print(f\"{c.get('id',''):<6}  {c.get('condition_template_id',''):<20}  {c.get('name','')}  {params}\")
"
}

# List catalog labels referenced by BannedLabels curation conditions.
# The Catalog GraphQL API only supports getLabel(name: "...") — there is no
# list-all endpoint — so we derive label names from the Xray conditions API,
# then resolve each via getLabel for full details.
# An optional [filter] substring matches against condition name OR label name.
# Usage: ./demo.sh list-catalog-labels [filter]
cmd_list_catalog_labels() {
  local filter="${1:-}"
  parse_jfrog_creds

  echo "==> Resolving catalog labels from BannedLabels conditions on ${JFROG_URL}..."

  local conditions_resp
  conditions_resp=$(jfrog_get "/xray/api/v1/curation/conditions") || conditions_resp="[]"

  # Emit tab-separated (condition_name, label_name) pairs from BannedLabels conditions.
  local pairs
  pairs=$(echo "${conditions_resp}" | python3 -c "
import json, sys
r = json.load(sys.stdin)
conditions = r.get('data', r) if isinstance(r, dict) else r
for c in conditions:
    if c.get('condition_template_id') != 'BannedLabels':
        continue
    cname = c.get('name', '')
    for p in c.get('param_values', []):
        for lbl in (p.get('value') or []):
            print(f'{cname}\t{lbl}')
" 2>/dev/null || true)

  if [[ -z "${pairs}" ]]; then
    echo "No BannedLabels conditions found — no catalog labels to display."
    return 0
  fi

  # Header
  printf "%-30s  %-30s  %s\n" "Condition name" "Label name" "Label description"
  printf "%s\n" "$(printf '%0.s-' {1..90})"

  local found=0
  while IFS=$'\t' read -r cname lbl; do
    # Filter: substring must appear in condition name OR label name (case-sensitive).
    if [[ -n "${filter}" && "${cname}" != *"${filter}"* && "${lbl}" != *"${filter}"* ]]; then
      continue
    fi
    found=1
    local gql_resp
    gql_resp=$(jfrog_catalog_graphql \
      "{\"query\":\"query { customCatalogLabel { getLabel(name: \\\"${lbl}\\\") { name description } } }\"}")
    local desc
    desc=$(echo "${gql_resp}" | python3 -c "
import json, sys
r = json.load(sys.stdin)
l = ((r.get('data') or {}).get('customCatalogLabel') or {}).get('getLabel') or {}
print(l.get('description', '(not found in catalog)'))
" 2>/dev/null || echo "(lookup failed)")
    printf "%-30s  %-30s  %s\n" "${cname}" "${lbl}" "${desc}"
  done <<< "${pairs}"

  if [[ "${found}" -eq 0 ]]; then
    echo "No labels matched filter '${filter}'."
  fi
}

# Create a BannedLabels curation condition and print the assigned ID.
# condition_name defaults to "demo-banned-label"; label_name defaults to
# condition_name with the "-label" suffix stripped (e.g. "demo-banned").
# The label is created via the Catalog GraphQL API if it doesn't exist (idempotent).
cmd_create_curation_condition() {
  local condition_name="${1:-demo-banned-label}"
  local label_name="${2:-${condition_name%-label}}"
  parse_jfrog_creds

  ensure_catalog_label "${label_name}"

  echo "==> Creating BannedLabels condition '${condition_name}' (label: '${label_name}')..."
  local condition_id
  condition_id=$(create_curation_condition "${condition_name}" "${label_name}")

  if [[ -z "${condition_id}" ]]; then
    echo "Error: failed to create condition." >&2
    exit 1
  fi

  echo ""
  echo "  Condition '${condition_name}' created — ID: ${condition_id}"
  echo ""
  echo "  Add to your demo .tfvars:"
  echo "    curation_banned_label_condition_id = \"${condition_id}\""
  echo ""
  echo "  Then apply:"
  echo "    ./$(basename "$0") create <demo-name>"
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

case "${1:-}" in
  bootstrap)                   shift; cmd_bootstrap "$@" ;;
  init-base)                   shift; cmd_init_base "$@" ;;
  destroy-base)                shift; cmd_destroy_base "$@" ;;
  create)                      shift; cmd_create "$@" ;;
  destroy)                     shift; cmd_destroy "$@" ;;
  plan)                        shift; cmd_plan "$@" ;;
  status)                      shift; cmd_status "$@" ;;
  output)                      shift; cmd_output "$@" ;;
  list)                        cmd_list ;;
  list-curation-conditions)    cmd_list_curation_conditions ;;
  list-catalog-labels)         shift; cmd_list_catalog_labels "$@" ;;
  create-curation-condition)   shift; cmd_create_curation_condition "$@" ;;
  *)                           usage ;;
esac
