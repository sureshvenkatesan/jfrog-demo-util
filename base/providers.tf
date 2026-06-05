terraform {
  required_version = ">= 1.7"

  backend "http" {}

  required_providers {
    xray = {
      source  = "jfrog/xray"
      version = "~> 3.1"
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

provider "platform" {
  url          = var.jfrog_url
  access_token = var.jfrog_access_token
}
