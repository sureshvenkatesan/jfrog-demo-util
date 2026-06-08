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

output "curation_dryrun_policy_names" {
  description = "Names of all DRYRUN (audit-only) curation policies created for this demo."
  value       = { for k, v in xray_curation_policy.dryrun : k => v.name }
}

output "curation_block_policy_names" {
  description = "Names of all BLOCK (enforcement) curation policies created for this demo."
  value       = { for k, v in xray_curation_policy.block : k => v.name }
}
