terraform {
  required_providers {
    platform = {
      source  = "jfrog/platform"
      version = "~> 2.2"
    }
  }
}

resource "platform_workers_service" "block_if_not_scanned" {
  key         = var.worker_key
  enabled     = var.enabled
  description = var.description
  source_code = file("${path.module}/workers/block-if-not-scanned.ts")
  action      = "BEFORE_DOWNLOAD"

  filter_criteria = {
    artifact_filter_criteria = {
      repo_keys = var.repo_keys
    }
  }
}
