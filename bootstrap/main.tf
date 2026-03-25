terraform {
  required_version = ">= 1.6"

  required_providers {
    artifactory = {
      source  = "jfrog/artifactory"
      version = "~> 12.11"
    }
  }
}

provider "artifactory" {
  url          = var.jfrog_url
  access_token = var.jfrog_access_token
}

resource "artifactory_local_terraformbackend_repository" "tfstate" {
  key         = var.state_repo_key
  description = "Terraform remote state storage for demo-util"
}
