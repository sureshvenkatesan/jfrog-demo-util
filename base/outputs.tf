output "worker_key" {
  description = "Key of the deployed SBOM service worker (null if disabled)."
  value       = var.enable_worker_webhook ? platform_workers_service.sbom[0].key : null
}

output "webhook_name" {
  description = "Name of the Xray scan-completed webhook (null if disabled)."
  value       = var.enable_worker_webhook ? xray_webhook.scan_completed[0].name : null
}

output "worker_execute_url" {
  description = "URL the webhook POSTs to when a scan completes (null if disabled)."
  value       = var.enable_worker_webhook ? local.worker_execute_url : null
}
