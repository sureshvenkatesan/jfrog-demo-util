output "state_repo_key" {
  description = "Key of the Terraform Backend repository created for remote state storage."
  value       = artifactory_local_terraformbackend_repository.tfstate.key
}
