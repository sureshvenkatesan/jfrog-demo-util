variables {
  jfrog_url              = "https://test-instance.jfrog.io"
  jfrog_access_token     = "test-token-value"
  enable_worker_webhook  = true
  worker_key             = "sbom-service"
  webhook_name           = "scanCompleted"
  webhook_url            = ""
}

run "worker_has_correct_key" {
  command = plan

  assert {
    condition     = platform_workers_service.sbom[0].key == "sbom-service"
    error_message = "Worker key must match var.worker_key."
  }

  assert {
    condition     = platform_workers_service.sbom[0].action == "GENERIC_EVENT"
    error_message = "Worker action must be GENERIC_EVENT."
  }

  assert {
    condition     = platform_workers_service.sbom[0].enabled == true
    error_message = "Worker must be enabled."
  }
}

run "webhook_has_correct_name" {
  command = plan

  assert {
    condition     = xray_webhook.scan_completed[0].name == "scanCompleted"
    error_message = "Webhook name must match var.webhook_name."
  }
}
