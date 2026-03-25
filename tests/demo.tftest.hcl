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

  enable_curation                 = true
  curation_malicious_condition_id = "1"
  curation_immature_condition_id  = "16"
  curation_cvss_condition_id      = "3"
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

run "curation_policies_are_prefixed" {
  command = plan

  assert {
    condition     = xray_curation_policy.malicious[0].name == "testdemo-curation-malicious"
    error_message = "Malicious curation policy name must include demo_name."
  }

  assert {
    condition     = xray_curation_policy.immature[0].name == "testdemo-curation-immature"
    error_message = "Immature curation policy name must include demo_name."
  }

  assert {
    condition     = xray_curation_policy.cvss[0].name == "testdemo-curation-cvss-9"
    error_message = "CVSS curation policy name must include demo_name."
  }
}
