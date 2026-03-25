variable "jfrog_url" {
  description = "Base URL of the JFrog Platform instance (e.g. https://mycompany.jfrog.io)."
  type        = string
}

variable "jfrog_access_token" {
  description = "JFrog access token with admin permissions to create repositories."
  type        = string
  sensitive   = true
}

variable "state_repo_key" {
  description = "Repository key for the Terraform Backend state repository."
  type        = string
  default     = "demo-util-tfstate"
}
