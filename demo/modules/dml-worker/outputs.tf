output "worker_key" {
  description = "Key of the deployed block-if-not-scanned worker."
  value       = platform_workers_service.block_if_not_scanned.key
}
