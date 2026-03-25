resource "platform_workers_service" "sbom" {
  count = var.enable_worker_webhook ? 1 : 0

  key         = var.worker_key
  enabled     = true
  description = "SBOM service worker: generates CycloneDX SBOMs from Xray webhook payloads."
  source_code = file("${path.module}/workers/sbom-service.ts")
  action      = "GENERIC_EVENT"
}

resource "xray_webhook" "scan_completed" {
  count = var.enable_worker_webhook ? 1 : 0

  name = var.webhook_name
  url  = local.worker_execute_url

  headers = {
    Authorization = "Bearer ${var.jfrog_access_token}"
  }
}
