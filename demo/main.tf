locals {
  # Cross-product of environments × local repo definitions, carrying package_type
  env_local_repos = {
    for pair in setproduct(var.environments, keys(var.local_repos)) :
    "${pair[0]}-${pair[1]}" => {
      env          = pair[0]
      suffix       = pair[1]
      package_type = var.local_repos[pair[1]]
      repo_key     = "${var.demo_name}-${pair[0]}-${pair[1]}"
    }
  }

  # Filter local repos by package type for typed resources
  local_generic_repos = { for k, v in local.env_local_repos : k => v if v.package_type == "generic" }
  local_npm_repos     = { for k, v in local.env_local_repos : k => v if v.package_type == "npm" }
  local_pypi_repos    = { for k, v in local.env_local_repos : k => v if v.package_type == "pypi" }
  local_maven_repos   = { for k, v in local.env_local_repos : k => v if v.package_type == "maven" }
  local_gradle_repos  = { for k, v in local.env_local_repos : k => v if v.package_type == "gradle" }
  local_go_repos      = { for k, v in local.env_local_repos : k => v if v.package_type == "go" }
  local_nuget_repos   = { for k, v in local.env_local_repos : k => v if v.package_type == "nuget" }
  local_docker_repos  = { for k, v in local.env_local_repos : k => v if v.package_type == "docker" }
  local_conan_repos   = { for k, v in local.env_local_repos : k => v if v.package_type == "conan" }
  local_conda_repos   = { for k, v in local.env_local_repos : k => v if v.package_type == "conda" }
  local_ivy_repos     = { for k, v in local.env_local_repos : k => v if v.package_type == "ivy" }

  # Filter remote repos by package type for typed resources
  generic_repos = { for k, v in var.remote_repos : k => v if v.package_type == "generic" }
  npm_repos     = { for k, v in var.remote_repos : k => v if v.package_type == "npm" }
  pypi_repos    = { for k, v in var.remote_repos : k => v if v.package_type == "pypi" }
  maven_repos   = { for k, v in var.remote_repos : k => v if v.package_type == "maven" }
  gradle_repos  = { for k, v in var.remote_repos : k => v if v.package_type == "gradle" }
  go_repos      = { for k, v in var.remote_repos : k => v if v.package_type == "go" }
  nuget_repos   = { for k, v in var.remote_repos : k => v if v.package_type == "nuget" }
  docker_repos  = { for k, v in var.remote_repos : k => v if v.package_type == "docker" }
  conan_repos   = { for k, v in var.remote_repos : k => v if v.package_type == "conan" }
  conda_repos   = { for k, v in var.remote_repos : k => v if v.package_type == "conda" }
  ivy_repos     = { for k, v in var.remote_repos : k => v if v.package_type == "ivy" }

  # Collect all local repo keys across all typed resources
  all_local_repo_keys = merge(
    { for k, v in artifactory_local_generic_repository.demo : k => v.key },
    { for k, v in artifactory_local_npm_repository.demo : k => v.key },
    { for k, v in artifactory_local_pypi_repository.demo : k => v.key },
    { for k, v in artifactory_local_maven_repository.demo : k => v.key },
    { for k, v in artifactory_local_gradle_repository.demo : k => v.key },
    { for k, v in artifactory_local_go_repository.demo : k => v.key },
    { for k, v in artifactory_local_nuget_repository.demo : k => v.key },
    { for k, v in artifactory_local_docker_v2_repository.demo : k => v.key },
    { for k, v in artifactory_local_conan_repository.demo : k => v.key },
    { for k, v in artifactory_local_conda_repository.demo : k => v.key },
    { for k, v in artifactory_local_ivy_repository.demo : k => v.key },
  )

  # Collect all remote repo keys across all typed resources
  all_remote_repo_keys = merge(
    { for k, v in artifactory_remote_generic_repository.demo : k => v.key },
    { for k, v in artifactory_remote_npm_repository.demo : k => v.key },
    { for k, v in artifactory_remote_pypi_repository.demo : k => v.key },
    { for k, v in artifactory_remote_maven_repository.demo : k => v.key },
    { for k, v in artifactory_remote_gradle_repository.demo : k => v.key },
    { for k, v in artifactory_remote_go_repository.demo : k => v.key },
    { for k, v in artifactory_remote_nuget_repository.demo : k => v.key },
    { for k, v in artifactory_remote_docker_repository.demo : k => v.key },
    { for k, v in artifactory_remote_conan_repository.demo : k => v.key },
    { for k, v in artifactory_remote_conda_repository.demo : k => v.key },
    { for k, v in artifactory_remote_ivy_repository.demo : k => v.key },
  )

  # Effective group name for curation waiver decision owners.
  # Falls back to "<demo_name>-curation-waiver" when the variable is left empty.
  curation_group_name = coalesce(var.curation_decision_owner_group, "${var.demo_name}-curation-waiver")

  # Curation condition map – drives two for_each resources (dryrun + block).
  # owners = [] means no decision_owners (waiver forbidden); non-empty list
  # means the curation waiver group is assigned as decision owner.
  # CUR_BANNED_LABEL is optional: included only when a condition ID is supplied.
  curation_conditions = merge(
    {
      "CUR_MALICIOUS" = {
        condition_id = var.curation_malicious_condition_id
        waiver       = "forbidden"
        owners       = []
      }
      "CUR_OPR_IMMATURE" = {
        condition_id = var.curation_immature_condition_id
        waiver       = "manual"
        owners       = [local.curation_group_name]
      }
      "CUR_OPR_AGED" = {
        condition_id = var.curation_aged_condition_id
        waiver       = "manual"
        owners       = [local.curation_group_name]
      }
      "CUR_CVE_CRITICAL" = {
        condition_id = var.curation_critical_condition_id
        waiver       = "manual"
        owners       = [local.curation_group_name]
      }
      "CUR_NO_LICENSE" = {
        condition_id = var.curation_no_license_condition_id
        waiver       = "manual"
        owners       = [local.curation_group_name]
      }
      "CUR_NO_DOCKERHUB" = {
        condition_id = var.curation_no_dockerhub_condition_id
        waiver       = "manual"
        owners       = [local.curation_group_name]
      }
    },
    var.curation_banned_label_condition_id != "" ? {
      "CUR_BANNED_LABEL" = {
        condition_id = var.curation_banned_label_condition_id
        waiver       = "forbidden"
        owners       = []
      }
    } : {}
  )

  # Collect all virtual repo keys (only for types that have at least one repo)
  all_virtual_repo_keys = {
    for type, repos in {
      "generic" = artifactory_virtual_generic_repository.demo
      "npm"     = artifactory_virtual_npm_repository.demo
      "pypi"    = artifactory_virtual_pypi_repository.demo
      "maven"   = artifactory_virtual_maven_repository.demo
      "gradle"  = artifactory_virtual_gradle_repository.demo
      "go"      = artifactory_virtual_go_repository.demo
      "nuget"   = artifactory_virtual_nuget_repository.demo
      "docker"  = artifactory_virtual_docker_repository.demo
      "conan"   = artifactory_virtual_conan_repository.demo
      "conda"   = artifactory_virtual_conda_repository.demo
      "ivy"     = artifactory_virtual_ivy_repository.demo
    } : type => repos[0].key if length(repos) > 0
  }
}

# ---------------------------------------------------------------------------
# JFrog Project
# ---------------------------------------------------------------------------

resource "project" "demo" {
  key          = var.demo_name
  display_name = "${var.jfrog_username}-${var.demo_name}"
  description  = "Demo project for ${var.demo_name}"

  admin_privileges {
    manage_members   = true
    manage_resources = true
    index_resources  = true
  }
}

# ---------------------------------------------------------------------------
# Local Repositories (typed, one per environment x repo definition)
# ---------------------------------------------------------------------------

resource "artifactory_local_generic_repository" "demo" {
  for_each             = local.local_generic_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_npm_repository" "demo" {
  for_each             = local.local_npm_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_pypi_repository" "demo" {
  for_each             = local.local_pypi_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_maven_repository" "demo" {
  for_each             = local.local_maven_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_gradle_repository" "demo" {
  for_each             = local.local_gradle_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_go_repository" "demo" {
  for_each             = local.local_go_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_nuget_repository" "demo" {
  for_each             = local.local_nuget_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_docker_v2_repository" "demo" {
  for_each             = local.local_docker_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_conan_repository" "demo" {
  for_each             = local.local_conan_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_conda_repository" "demo" {
  for_each             = local.local_conda_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_local_ivy_repository" "demo" {
  for_each             = local.local_ivy_repos
  key                  = each.value.repo_key
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

# ---------------------------------------------------------------------------
# Remote Repositories (typed, with optional Curation)
# ---------------------------------------------------------------------------

resource "artifactory_remote_generic_repository" "demo" {
  for_each                = local.generic_repos
  key                     = "${var.demo_name}-${each.key}"
  url                     = each.value.url
  project_key             = project.demo.key
  project_environments    = ["DEV"]
  xray_index              = true
  store_artifacts_locally = each.value.store_artifacts_locally
}

resource "artifactory_remote_npm_repository" "demo" {
  for_each             = local.npm_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_pypi_repository" "demo" {
  for_each             = local.pypi_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_maven_repository" "demo" {
  for_each             = local.maven_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_gradle_repository" "demo" {
  for_each             = local.gradle_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_go_repository" "demo" {
  for_each             = local.go_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_nuget_repository" "demo" {
  for_each             = local.nuget_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_docker_repository" "demo" {
  for_each             = local.docker_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_conan_repository" "demo" {
  for_each             = local.conan_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
  curated              = var.enable_curation
}

resource "artifactory_remote_conda_repository" "demo" {
  for_each             = local.conda_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

resource "artifactory_remote_ivy_repository" "demo" {
  for_each             = local.ivy_repos
  key                  = "${var.demo_name}-${each.key}"
  url                  = each.value.url
  project_key          = project.demo.key
  project_environments = ["DEV"]
  xray_index           = true
}

# ---------------------------------------------------------------------------
# Virtual Repositories (one typed virtual per package type in use)
# ---------------------------------------------------------------------------

resource "artifactory_virtual_generic_repository" "demo" {
  count                   = length(local.local_generic_repos) + length(local.generic_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-generic-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_generic_repository.demo["dev-generic-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_generic_repository.demo : r.key],
    [for r in artifactory_remote_generic_repository.demo : r.key],
  )
}

resource "artifactory_virtual_npm_repository" "demo" {
  count                   = length(local.local_npm_repos) + length(local.npm_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-npm-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_npm_repository.demo["dev-npm-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_npm_repository.demo : r.key],
    [for r in artifactory_remote_npm_repository.demo : r.key],
  )
}

resource "artifactory_virtual_pypi_repository" "demo" {
  count                   = length(local.local_pypi_repos) + length(local.pypi_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-pypi-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_pypi_repository.demo["dev-pypi-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_pypi_repository.demo : r.key],
    [for r in artifactory_remote_pypi_repository.demo : r.key],
  )
}

resource "artifactory_virtual_maven_repository" "demo" {
  count                   = length(local.local_maven_repos) + length(local.maven_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-maven-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_maven_repository.demo["dev-maven-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_maven_repository.demo : r.key],
    [for r in artifactory_remote_maven_repository.demo : r.key],
  )
}

resource "artifactory_virtual_gradle_repository" "demo" {
  count                   = length(local.local_gradle_repos) + length(local.gradle_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-gradle-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_gradle_repository.demo["dev-gradle-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_gradle_repository.demo : r.key],
    [for r in artifactory_remote_gradle_repository.demo : r.key],
  )
}

resource "artifactory_virtual_go_repository" "demo" {
  count                   = length(local.local_go_repos) + length(local.go_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-go-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_go_repository.demo["dev-go-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_go_repository.demo : r.key],
    [for r in artifactory_remote_go_repository.demo : r.key],
  )
}

resource "artifactory_virtual_nuget_repository" "demo" {
  count                   = length(local.local_nuget_repos) + length(local.nuget_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-nuget-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_nuget_repository.demo["dev-nuget-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_nuget_repository.demo : r.key],
    [for r in artifactory_remote_nuget_repository.demo : r.key],
  )
}

resource "artifactory_virtual_docker_repository" "demo" {
  count                   = length(local.local_docker_repos) + length(local.docker_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-docker-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_docker_v2_repository.demo["dev-docker-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_docker_v2_repository.demo : r.key],
    [for r in artifactory_remote_docker_repository.demo : r.key],
  )
}

resource "artifactory_virtual_conan_repository" "demo" {
  count                   = length(local.local_conan_repos) + length(local.conan_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-conan-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_conan_repository.demo["dev-conan-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_conan_repository.demo : r.key],
    [for r in artifactory_remote_conan_repository.demo : r.key],
  )
}

resource "artifactory_virtual_conda_repository" "demo" {
  count                   = length(local.local_conda_repos) + length(local.conda_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-conda-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_conda_repository.demo["dev-conda-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_conda_repository.demo : r.key],
    [for r in artifactory_remote_conda_repository.demo : r.key],
  )
}

resource "artifactory_virtual_ivy_repository" "demo" {
  count                   = length(local.local_ivy_repos) + length(local.ivy_repos) > 0 ? 1 : 0
  key                     = "${var.demo_name}-ivy-virtual"
  project_key             = project.demo.key
  default_deployment_repo = try(artifactory_local_ivy_repository.demo["dev-ivy-local"].key, null)
  repositories = concat(
    [for r in artifactory_local_ivy_repository.demo : r.key],
    [for r in artifactory_remote_ivy_repository.demo : r.key],
  )
}

# ---------------------------------------------------------------------------
# Xray Security Policy – Dry Run (audit only)
# ---------------------------------------------------------------------------

resource "xray_security_policy" "dry_run" {
  name        = "${var.demo_name}-dry-run"
  description = ""
  type        = "security"
  project_key = project.demo.key

  rule {
    name     = "malicious-packages"
    priority = 1

    criteria {
      malicious_package = true
    }

    actions {
      notify_deployer         = false
      notify_watch_recipients = false

      block_download {
        unscanned = false
        active    = false
      }
    }
  }

  rule {
    name     = "cve-high"
    priority = 2

    criteria {
      min_severity          = "High"
      fix_version_dependant = true
    }

    actions {
      notify_deployer         = false
      notify_watch_recipients = false

      block_download {
        unscanned = false
        active    = false
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Xray Security Policy – Block (enforcement)
# ---------------------------------------------------------------------------

resource "xray_security_policy" "block" {
  name        = "${var.demo_name}-block"
  description = ""
  type        = "security"
  project_key = project.demo.key

  rule {
    name     = "malicious-packages"
    priority = 1

    criteria {
      malicious_package = true
    }

    actions {
      notify_deployer         = true
      notify_watch_recipients = true
      fail_build              = true

      block_download {
        unscanned = true
        active    = true
      }
    }
  }

  rule {
    name     = "cve-high"
    priority = 2

    criteria {
      min_severity          = "High"
      fix_version_dependant = true
    }

    actions {
      notify_deployer         = true
      notify_watch_recipients = true
      fail_build              = true

      block_download {
        unscanned = true
        active    = true
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Xray Watch – Dry Run
# ---------------------------------------------------------------------------

resource "xray_watch" "dry_run" {
  name        = "${var.demo_name}-dry-run-watch"
  active      = true
  project_key = project.demo.key

  watch_resource {
    type = "all-repos"
  }

  assigned_policy {
    name = xray_security_policy.dry_run.name
    type = "security"
  }
}

# ---------------------------------------------------------------------------
# Xray Watch – Block
# ---------------------------------------------------------------------------

resource "xray_watch" "block" {
  name        = "${var.demo_name}-block-watch"
  active      = true
  project_key = project.demo.key

  watch_resource {
    type = "all-repos"
  }

  assigned_policy {
    name = xray_security_policy.block.name
    type = "security"
  }
}

# ---------------------------------------------------------------------------
# Curation Policies (scoped to curated remote repos)
#
# repo_include is provided via demo/curation_override.tf.json, auto-generated
# by demo.sh. The xray provider's ValidateConfig rejects any non-literal value
# for repo_include (variables, locals, for-expressions are all unknown at that
# phase). The override file supplies literal repo keys that the validator
# accepts. See: https://github.com/jfrog/terraform-provider-xray/issues/377
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Curation waiver group
# ---------------------------------------------------------------------------

resource "platform_group" "curation_waiver" {
  count = var.enable_curation ? 1 : 0

  name        = local.curation_group_name
  description = "Decision owners for ${var.demo_name} curation waiver requests"
  auto_join   = false
}

# ---------------------------------------------------------------------------
# Curation Policies – DRYRUN tier (audit-only, all curated remote repos)
#
# repo_include is injected via curation_override.tf.json (generated by
# demo.sh) because the xray provider's ValidateConfig rejects non-literal
# values for that field at plan time.
# See: https://github.com/jfrog/terraform-provider-xray/issues/377
# ---------------------------------------------------------------------------

resource "xray_curation_policy" "dryrun" {
  for_each = var.enable_curation ? local.curation_conditions : {}

  name                  = "${var.demo_name}-${each.key}_DRYRUN"
  condition_id          = each.value.condition_id
  scope                 = "specific_repos"
  policy_action         = "dry_run"
  waiver_request_config = "forbidden"
  decision_owners       = length(each.value.owners) > 0 ? each.value.owners : null

  depends_on = [
    platform_group.curation_waiver,
    artifactory_remote_npm_repository.demo,
    artifactory_remote_pypi_repository.demo,
    artifactory_remote_maven_repository.demo,
    artifactory_remote_gradle_repository.demo,
    artifactory_remote_go_repository.demo,
    artifactory_remote_nuget_repository.demo,
    artifactory_remote_docker_repository.demo,
    artifactory_remote_conan_repository.demo,
    artifactory_remote_conda_repository.demo,
    artifactory_remote_ivy_repository.demo,
  ]
}

# ---------------------------------------------------------------------------
# Curation Policies – BLOCK tier (enforcement, scoped repos only)
#
# When curation_block_repos is non-empty, repo_include is injected via the
# override file, and scope is "specific_repos". When it is empty, BLOCK
# policies default to "all_repos" scope (global enforcement).
# repo_include for non-empty curation_block_repos is injected by demo.sh.
# ---------------------------------------------------------------------------

resource "xray_curation_policy" "block" {
  for_each = var.enable_curation ? local.curation_conditions : {}

  name                  = "${var.demo_name}-${each.key}_BLOCK"
  condition_id          = each.value.condition_id
  scope                 = length(var.curation_block_repos) > 0 ? "specific_repos" : "all_repos"
  policy_action         = "block"
  waiver_request_config = each.value.waiver
  decision_owners       = length(each.value.owners) > 0 ? each.value.owners : null

  depends_on = [
    platform_group.curation_waiver,
    artifactory_remote_npm_repository.demo,
    artifactory_remote_pypi_repository.demo,
    artifactory_remote_maven_repository.demo,
    artifactory_remote_gradle_repository.demo,
    artifactory_remote_go_repository.demo,
    artifactory_remote_nuget_repository.demo,
    artifactory_remote_docker_repository.demo,
    artifactory_remote_conan_repository.demo,
    artifactory_remote_conda_repository.demo,
    artifactory_remote_ivy_repository.demo,
  ]
}

# ---------------------------------------------------------------------------
# Optional DML Worker (block-if-not-scanned)
# ---------------------------------------------------------------------------

module "dml_worker" {
  source = "./modules/dml-worker"
  count  = var.enable_dml_worker ? 1 : 0

  worker_key = "${var.demo_name}-block-if-not-scanned"
  repo_keys = (
    length(var.dml_worker_repo_keys) > 0
    ? var.dml_worker_repo_keys
    : values(local.all_local_repo_keys)
  )
}
