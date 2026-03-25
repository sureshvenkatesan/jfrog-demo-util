variable "worker_key" {
  description = "Unique key for the block-if-not-scanned worker."
  type        = string
  default     = "block-if-not-scanned"
}

variable "enabled" {
  description = "Whether the worker is enabled."
  type        = bool
  default     = true
}

variable "description" {
  description = "Human-readable description for the worker."
  type        = string
  default     = "Blocks artifact downloads unless the 'approved' property is set to true."
}

variable "repo_keys" {
  description = "List of Artifactory repository keys the worker applies to."
  type        = list(string)

  validation {
    condition     = length(var.repo_keys) > 0
    error_message = "repo_keys must contain at least one repository key."
  }
}
