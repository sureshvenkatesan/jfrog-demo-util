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

# ---------------------------------------------------------------------------
# Remote backend initialisation (Artifactory Terraform Backend repo)
#
# URL pattern:
#   https://<instance>/artifactory/api/terraform/state/<repo-key>/<state-name>
# ---------------------------------------------------------------------------

init_demo() {
  local state_name="$1"
  local state_url="${JFROG_URL}/artifactory/${STATE_REPO}/${state_name}/terraform.tfstate"
  local init_log
  init_log=$(mktemp)

  if ! terraform -chdir="${DEMO_DIR}" init -reconfigure \
    -backend-config="address=${state_url}" \
    -backend-config="update_method=PUT" \
    > "${init_log}" 2>&1; then
    echo "Error: terraform init failed for demo '${state_name}':" >&2
    cat "${init_log}" >&2
    rm -f "${init_log}"
    exit 1
  fi
  rm -f "${init_log}"
}

init_base() {
  local state_url="${JFROG_URL}/artifactory/${STATE_REPO}/base/terraform.tfstate"
  local init_log
  init_log=$(mktemp)

  if ! terraform -chdir="${BASE_DIR}" init -reconfigure \
    -backend-config="address=${state_url}" \
    -backend-config="update_method=PUT" \
    > "${init_log}" 2>&1; then
    echo "Error: terraform init failed for base module:" >&2
    cat "${init_log}" >&2
    rm -f "${init_log}"
    exit 1
  fi
  rm -f "${init_log}"
}

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
  demo_name=$(grep -E '^\s*demo_name\s*=' "${tfvars}" | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/')

  # Only include remote repos whose package_type is supported by JFrog Curation.
  local keys=()
  while IFS= read -r suffix; do
    [[ -n "${suffix}" ]] && keys+=("\"${demo_name}-${suffix}\"")
  done < <(python3 -c "
import re, sys
with open(sys.argv[1]) as f:
    content = f.read()
supported = {'npm', 'pypi', 'maven', 'gradle', 'go', 'nuget'}
for m in re.finditer(
    r'\"([^\"]*-remote)\"\s*=\s*\{[^}]*package_type\s*=\s*\"(\w+)\"',
    content, re.DOTALL,
):
    key, pkg = m.groups()
    if pkg in supported:
        print(key)
" "${tfvars}")

  if [[ ${#keys[@]} -eq 0 ]]; then
    rm -f "${out}"
    return
  fi

  local json_array
  json_array=$(IFS=,; echo "${keys[*]}")

  cat > "${out}" <<EOFJ
{
  "resource": {
    "xray_curation_policy": {
      "malicious": { "repo_include": [${json_array}] },
      "immature":  { "repo_include": [${json_array}] },
      "cvss":      { "repo_include": [${json_array}] }
    }
  }
}
EOFJ
}

# ---------------------------------------------------------------------------
# Demo lifecycle
# ---------------------------------------------------------------------------

cmd_create() {
  local name="${1:?demo name required}"
  ensure_demo_tfvars "${name}"
  parse_jfrog_creds

  echo "==> Initializing demo module for '${name}'..."
  init_demo "${name}"
  generate_curation_override "${name}"

  echo "==> Applying demo '${name}'..."
  terraform -chdir="${DEMO_DIR}" apply \
    $(base_var_file_args) \
    -var-file="${DEMOS_DIR}/${name}.tfvars" \
    "${@:2}"

  echo ""
  echo "Demo '${name}' is ready."
  terraform -chdir="${DEMO_DIR}" output
}

cmd_destroy() {
  local name="${1:?demo name required}"
  ensure_demo_tfvars "${name}"
  parse_jfrog_creds

  init_demo "${name}"
  generate_curation_override "${name}"

  # JFrog auto-creates a <demo_name>-build-info repository when a project is
  # provisioned. This repo is project-locked (cannot be detached or deleted
  # independently), and the standard project DELETE API returns 400 "Project
  # containing resources can't be removed" because of it. The only way to clean
  # it up is to use DELETE /access/api/v1/projects/{key}?deleteRepos=true, which
  # atomically removes the build-info repo and the project in one call.
  # We do this before running terraform destroy so the project.demo resource
  # deletion (which calls the standard DELETE without the flag) doesn't fail.
  local demo_name
  demo_name=$(grep -E '^\s*demo_name\s*=' "${DEMOS_DIR}/${name}.tfvars" | head -1 \
    | sed 's/.*= *"\([^"]*\)".*/\1/')
  local project_url="${JFROG_URL}/access/api/v1/projects/${demo_name}?deleteRepos=true"
  echo "==> Pre-deleting JFrog project '${demo_name}' (removes auto-created build-info repo)..."
  if curl -sf -X DELETE -H "Authorization: Bearer ${JFROG_TOKEN}" "${project_url}" \
       2>/dev/null; then
    echo "Project '${demo_name}' deleted via API."
  else
    echo "Project '${demo_name}' already gone or not found – continuing."
  fi

  echo "==> Destroying demo '${name}' Terraform resources..."
  terraform -chdir="${DEMO_DIR}" destroy \
    $(base_var_file_args) \
    -var-file="${DEMOS_DIR}/${name}.tfvars" \
    "${@:2}"

  # Remove the entire remote state folder so this demo no longer appears in
  # `list`. Deleting the folder (not just the .tfstate file) avoids the
  # Artifactory empty-folder ghost that the storage listing still returns.
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

  init_demo "${name}"
  generate_curation_override "${name}"

  terraform -chdir="${DEMO_DIR}" plan \
    $(base_var_file_args) \
    -var-file="${DEMOS_DIR}/${name}.tfvars" \
    "${@:2}"
}

cmd_status() {
  local name="${1:?demo name required}"
  parse_jfrog_creds

  init_demo "${name}"
  generate_curation_override "${name}"
  terraform -chdir="${DEMO_DIR}" show
}

cmd_output() {
  local name="${1:?demo name required}"
  parse_jfrog_creds

  init_demo "${name}"
  generate_curation_override "${name}"
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
# Dispatch
# ---------------------------------------------------------------------------

case "${1:-}" in
  bootstrap)    shift; cmd_bootstrap "$@" ;;
  init-base)    shift; cmd_init_base "$@" ;;
  destroy-base) shift; cmd_destroy_base "$@" ;;
  create)       shift; cmd_create "$@" ;;
  destroy)      shift; cmd_destroy "$@" ;;
  plan)         shift; cmd_plan "$@" ;;
  status)       shift; cmd_status "$@" ;;
  output)       shift; cmd_output "$@" ;;
  list)         cmd_list ;;
  *)            usage ;;
esac
