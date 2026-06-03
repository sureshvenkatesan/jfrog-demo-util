variable "jfrog_url" {
  description = "Base URL of the JFrog Platform instance."
  type        = string

  validation {
    condition     = can(regex("^https?://", var.jfrog_url))
    error_message = "jfrog_url must start with http:// or https://."
  }
}

variable "jfrog_access_token" {
  description = "Access token for authenticating with the JFrog Platform APIs."
  type        = string
  sensitive   = true
}

variable "jfrog_username" {
  description = "JFrog username extracted from the access token. Used in project display name."
  type        = string
}

variable "demo_name" {
  description = "Short identifier for this demo (used as project key and resource name prefix). Must be 2-32 lowercase alphanumeric characters or hyphens, starting with a letter."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,31}$", var.demo_name))
    error_message = "demo_name must be 2-32 lowercase alphanumeric characters or hyphens, starting with a letter."
  }
}

variable "environments" {
  description = "List of environment names. One local repository is created per environment for each entry in local_repos."
  type        = list(string)
  default     = ["dev", "qa", "prod"]

  validation {
    condition     = length(var.environments) > 0
    error_message = "At least one environment must be specified."
  }
}

variable "local_repos" {
  description = "Map of local repository suffix to package type. Keys must end in '-local' (e.g. {\"npm-local\" = \"npm\"})."
  type        = map(string)
  default = {
    "generic-local" = "generic"
  }

  validation {
    condition     = alltrue([for k, _ in var.local_repos : endswith(k, "-local")])
    error_message = "All local_repos keys must end in '-local'."
  }

  validation {
    condition = alltrue([
      for k, v in var.local_repos :
      contains(["npm", "pypi", "maven", "gradle", "ivy", "docker", "go", "nuget", "conan", "conda", "generic"], v)
    ])
    error_message = "local_repos package type must be one of: npm, pypi, maven, gradle, ivy, docker, go, nuget, conan, conda, generic."
  }
}

variable "remote_repos" {
  description = "Map of remote repository suffix to config. Keys must end in '-remote'. package_type must be one of: npm, pypi, maven, docker, go, nuget, gems, gradle, generic. store_artifacts_locally only applies to generic repos (default true)."
  type = map(object({
    url                     = string
    package_type            = string
    store_artifacts_locally = optional(bool, true)
  }))
  default = {}

  validation {
    condition     = alltrue([for k, _ in var.remote_repos : endswith(k, "-remote")])
    error_message = "All remote_repos keys must end in '-remote'."
  }

  validation {
    condition = alltrue([
      for k, v in var.remote_repos :
      contains(["npm", "pypi", "maven", "ivy", "docker", "go", "nuget", "conan", "conda", "gems", "gradle", "generic"], v.package_type)
    ])
    error_message = "package_type must be one of: npm, pypi, maven, ivy, docker, go, nuget, conan, conda, gems, gradle, generic."
  }
}

variable "enable_curation" {
  description = "Whether to enable curation on remote repositories and create curation policies."
  type        = bool
  default     = true
}

variable "curation_malicious_condition_id" {
  description = "Condition ID for the built-in 'Malicious package' curation condition on your JFrog instance."
  type        = string
}

variable "curation_immature_condition_id" {
  description = "Condition ID for the 'Package version is immature (strict)' curation condition."
  type        = string
  default     = "16"
}

variable "curation_cvss_condition_id" {
  description = "Condition ID for the 'CVE with CVSS 9.0+' curation condition."
  type        = string
  default     = "3"
}

variable "curation_decision_owner_group" {
  description = "Artifactory group name for curation waiver decision owners (used by immature and CVSS policies)."
  type        = string
  default     = "Chaitanya-CurationWaiver-Demo"
}

variable "enable_dml_worker" {
  description = "Whether to deploy the block-if-not-scanned DML worker for this demo."
  type        = bool
  default     = false
}

variable "dml_worker_repo_keys" {
  description = "Repository keys the DML worker applies to (only used when enable_dml_worker is true)."
  type        = list(string)
  default     = []
}
