mock_provider "artifactory" {}
mock_provider "xray" {}
mock_provider "project" {}
mock_provider "platform" {}

variables {
  jfrog_url          = "https://test-instance.jfrog.io"
  jfrog_access_token = "test-token-value"
  jfrog_username     = "testuser"
  demo_name          = "testdemo"

  environments = ["dev", "qa", "prod"]

  local_repos = {
    "npm-local" = "npm"
  }

  remote_repos = {
    "npm-remote" = {
      url          = "https://registry.npmjs.org"
      package_type = "npm"
    }
  }

  enable_curation                    = true
  curation_malicious_condition_id    = "1"
  curation_immature_condition_id     = "14"
  curation_aged_condition_id         = "12"
  curation_critical_condition_id     = "3"
  curation_no_license_condition_id   = "8"
  curation_no_dockerhub_condition_id = "17"
  curation_banned_label_condition_id = ""
  curation_decision_owner_group      = "TestWaiverGroup"
  curation_block_repos               = []
  enable_dml_worker               = false
  dml_worker_repo_keys            = []
}

run "project_uses_demo_name_as_key" {
  command = plan

  assert {
    condition     = project.demo.key == "testdemo"
    error_message = "Project key must equal var.demo_name."
  }
}

run "typed_local_repo_per_environment" {
  command = plan

  assert {
    condition     = artifactory_local_npm_repository.demo["dev-npm-local"].key == "testdemo-dev-npm-local"
    error_message = "Dev npm local repo key must follow {demo_name}-{env}-{suffix} pattern."
  }

  assert {
    condition     = artifactory_local_npm_repository.demo["qa-npm-local"].key == "testdemo-qa-npm-local"
    error_message = "QA npm local repo key must follow {demo_name}-{env}-{suffix} pattern."
  }

  assert {
    condition     = artifactory_local_npm_repository.demo["prod-npm-local"].key == "testdemo-prod-npm-local"
    error_message = "Prod npm local repo key must follow {demo_name}-{env}-{suffix} pattern."
  }
}

run "remote_repo_has_curation_enabled" {
  command = plan

  assert {
    condition     = artifactory_remote_npm_repository.demo["npm-remote"].curated == true
    error_message = "Remote npm repo must have curation enabled when enable_curation is true."
  }

  assert {
    condition     = artifactory_remote_npm_repository.demo["npm-remote"].key == "testdemo-npm-remote"
    error_message = "Remote repo key must follow {demo_name}-{suffix} pattern."
  }
}

run "typed_virtual_repo_aggregates_matching_type" {
  command = plan

  assert {
    condition     = artifactory_virtual_npm_repository.demo[0].key == "testdemo-npm-virtual"
    error_message = "npm virtual repo key must be {demo_name}-npm-virtual."
  }
}

run "dry_run_policy_is_prefixed" {
  command = plan

  assert {
    condition     = xray_security_policy.dry_run.name == "testdemo-dry-run"
    error_message = "Dry-run security policy name must be {demo_name}-dry-run."
  }
}

run "block_policy_is_prefixed" {
  command = plan

  assert {
    condition     = xray_security_policy.block.name == "testdemo-block"
    error_message = "Block security policy name must be {demo_name}-block."
  }
}

run "dry_run_watch_is_active" {
  command = plan

  assert {
    condition     = xray_watch.dry_run.active == true
    error_message = "Dry-run watch must be active."
  }

  assert {
    condition     = xray_watch.dry_run.name == "testdemo-dry-run-watch"
    error_message = "Dry-run watch name must be {demo_name}-dry-run-watch."
  }
}

run "block_watch_is_active" {
  command = plan

  assert {
    condition     = xray_watch.block.active == true
    error_message = "Block watch must be active."
  }

  assert {
    condition     = xray_watch.block.name == "testdemo-block-watch"
    error_message = "Block watch name must be {demo_name}-block-watch."
  }
}

run "curation_policies_naming_and_actions" {
  command = plan

  assert {
    condition     = xray_curation_policy.dryrun["CUR_MALICIOUS"].name == "testdemo-CUR_MALICIOUS_DRYRUN"
    error_message = "Malicious DRYRUN policy name must be {demo_name}-CUR_MALICIOUS_DRYRUN."
  }

  assert {
    condition     = xray_curation_policy.block["CUR_MALICIOUS"].name == "testdemo-CUR_MALICIOUS_BLOCK"
    error_message = "Malicious BLOCK policy name must be {demo_name}-CUR_MALICIOUS_BLOCK."
  }

  assert {
    condition     = xray_curation_policy.dryrun["CUR_OPR_IMMATURE"].name == "testdemo-CUR_OPR_IMMATURE_DRYRUN"
    error_message = "Immature DRYRUN policy name must be {demo_name}-CUR_OPR_IMMATURE_DRYRUN."
  }

  assert {
    condition     = xray_curation_policy.block["CUR_OPR_IMMATURE"].name == "testdemo-CUR_OPR_IMMATURE_BLOCK"
    error_message = "Immature BLOCK policy name must be {demo_name}-CUR_OPR_IMMATURE_BLOCK."
  }

  assert {
    condition     = xray_curation_policy.dryrun["CUR_OPR_AGED"].name == "testdemo-CUR_OPR_AGED_DRYRUN"
    error_message = "Aged DRYRUN policy name must be {demo_name}-CUR_OPR_AGED_DRYRUN."
  }

  assert {
    condition     = xray_curation_policy.block["CUR_OPR_AGED"].name == "testdemo-CUR_OPR_AGED_BLOCK"
    error_message = "Aged BLOCK policy name must be {demo_name}-CUR_OPR_AGED_BLOCK."
  }

  assert {
    condition     = xray_curation_policy.dryrun["CUR_CVE_CRITICAL"].name == "testdemo-CUR_CVE_CRITICAL_DRYRUN"
    error_message = "Critical CVE DRYRUN policy name must be {demo_name}-CUR_CVE_CRITICAL_DRYRUN."
  }

  assert {
    condition     = xray_curation_policy.block["CUR_CVE_CRITICAL"].name == "testdemo-CUR_CVE_CRITICAL_BLOCK"
    error_message = "Critical CVE BLOCK policy name must be {demo_name}-CUR_CVE_CRITICAL_BLOCK."
  }

  assert {
    condition     = xray_curation_policy.dryrun["CUR_NO_LICENSE"].name == "testdemo-CUR_NO_LICENSE_DRYRUN"
    error_message = "No-license DRYRUN policy name must be {demo_name}-CUR_NO_LICENSE_DRYRUN."
  }

  assert {
    condition     = xray_curation_policy.block["CUR_NO_LICENSE"].name == "testdemo-CUR_NO_LICENSE_BLOCK"
    error_message = "No-license BLOCK policy name must be {demo_name}-CUR_NO_LICENSE_BLOCK."
  }

  assert {
    condition     = xray_curation_policy.dryrun["CUR_NO_DOCKERHUB"].name == "testdemo-CUR_NO_DOCKERHUB_DRYRUN"
    error_message = "No-DockerHub DRYRUN policy name must be {demo_name}-CUR_NO_DOCKERHUB_DRYRUN."
  }

  assert {
    condition     = xray_curation_policy.block["CUR_NO_DOCKERHUB"].name == "testdemo-CUR_NO_DOCKERHUB_BLOCK"
    error_message = "No-DockerHub BLOCK policy name must be {demo_name}-CUR_NO_DOCKERHUB_BLOCK."
  }

  assert {
    condition     = xray_curation_policy.dryrun["CUR_MALICIOUS"].policy_action == "dry_run"
    error_message = "DRYRUN policies must have policy_action = dry_run."
  }

  assert {
    condition     = xray_curation_policy.block["CUR_MALICIOUS"].policy_action == "block"
    error_message = "BLOCK policies must have policy_action = block."
  }
}
