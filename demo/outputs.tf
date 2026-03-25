output "project_key" {
  description = "Key of the JFrog Project created for this demo."
  value       = project.demo.key
}

output "local_repo_keys" {
  description = "Keys of local repositories created for this demo (one per environment x repo definition)."
  value       = local.all_local_repo_keys
}

output "remote_repo_keys" {
  description = "Keys of remote repositories created for this demo."
  value       = local.all_remote_repo_keys
}

output "virtual_repo_keys" {
  description = "Keys of virtual repositories created for this demo (one per package type)."
  value       = local.all_virtual_repo_keys
}

output "dry_run_policy_name" {
  description = "Name of the dry-run Xray security policy."
  value       = xray_security_policy.dry_run.name
}

output "block_policy_name" {
  description = "Name of the block Xray security policy."
  value       = xray_security_policy.block.name
}

output "dry_run_watch_name" {
  description = "Name of the dry-run Xray watch."
  value       = xray_watch.dry_run.name
}

output "block_watch_name" {
  description = "Name of the block Xray watch."
  value       = xray_watch.block.name
}

output "curation_malicious_name" {
  description = "Name of the malicious-package curation policy."
  value       = var.enable_curation ? xray_curation_policy.malicious[0].name : null
}

output "curation_immature_name" {
  description = "Name of the immature-package curation policy."
  value       = var.enable_curation ? xray_curation_policy.immature[0].name : null
}

output "curation_cvss_name" {
  description = "Name of the CVSS 9.0+ curation policy."
  value       = var.enable_curation ? xray_curation_policy.cvss[0].name : null
}
