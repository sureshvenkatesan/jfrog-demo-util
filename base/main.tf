resource "platform_workers_service" "sbom" {
  count = var.enable_worker_webhook ? 1 : 0

  key         = var.worker_key
  enabled     = true
  description = "SBOM service worker: generates CycloneDX SBOMs from Xray webhook payloads."
  source_code = file("${path.module}/workers/sbom-service.ts")
  # GENERIC_EVENT (HTTP-triggered) is the ideal action for Xray-webhook-driven
  # SBOM generation, but jfrog/platform provider <=2.2.x does not yet support it.
  # Use var.worker_action (default: AFTER_BUILD_INFO_SAVE) and update once
  # the provider adds GENERIC_EVENT to its schema validation.
  action = var.worker_action

  filter_criteria = {
    artifact_filter_criteria = {
      repo_keys = []
    }
  }
}

resource "xray_webhook" "scan_completed" {
  count = var.enable_worker_webhook ? 1 : 0

  name = var.webhook_name
  url  = local.worker_execute_url

  headers = {
    Authorization = "Bearer ${var.jfrog_access_token}"
  }
}
