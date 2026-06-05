terraform {
  required_version = ">= 1.7"

  backend "http" {}

  required_providers {
    xray = {
      source  = "jfrog/xray"
      version = "~> 3.1"
    }
    artifactory = {
      source  = "jfrog/artifactory"
      version = "~> 12.11"
    }
    project = {
      source  = "jfrog/project"
      version = "~> 1.0"
    }
    platform = {
      source  = "jfrog/platform"
      version = "~> 2.2"
    }
  }
}

provider "xray" {
  url          = var.jfrog_url
  access_token = var.jfrog_access_token
}

provider "artifactory" {
  url          = var.jfrog_url
  access_token = var.jfrog_access_token
}

provider "project" {
  url          = var.jfrog_url
  access_token = var.jfrog_access_token
}

provider "platform" {
  url          = var.jfrog_url
  access_token = var.jfrog_access_token
}
