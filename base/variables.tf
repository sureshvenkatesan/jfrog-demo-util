variable "jfrog_url" {
  description = "Base URL of the JFrog Platform instance (e.g. https://mycompany.jfrog.io)."
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

  validation {
    condition     = length(var.jfrog_access_token) > 0
    error_message = "jfrog_access_token must not be empty."
  }
}

variable "enable_worker_webhook" {
  description = "Whether to deploy the SBOM worker and Xray webhook. Set to true to enable."
  type        = bool
  default     = false
}

variable "worker_key" {
  description = "Unique key for the SBOM service worker (only used when enable_worker_webhook is true)."
  type        = string
  default     = "sbom-service"
}

variable "webhook_name" {
  description = "Name of the Xray webhook that triggers the SBOM worker on scan completion (only used when enable_worker_webhook is true)."
  type        = string
  default     = "scanCompleted"
}

variable "webhook_url" {
  description = "Internal URL the webhook POSTs to (the worker execute endpoint). Leave empty to auto-derive from worker_key. Only used when enable_worker_webhook is true."
  type        = string
  default     = ""
}

variable "worker_action" {
  description = "Worker action (event) that triggers the SBOM worker. Defaults to AFTER_BUILD_INFO_SAVE (fires when Artifactory receives build info, aligning with Xray scan results). Change to GENERIC_EVENT once jfrog/platform provider adds support for HTTP-triggered workers."
  type        = string
  default     = "AFTER_BUILD_INFO_SAVE"

  validation {
    condition = contains([
      "BEFORE_DOWNLOAD", "AFTER_DOWNLOAD", "BEFORE_UPLOAD", "AFTER_CREATE",
      "AFTER_BUILD_INFO_SAVE", "AFTER_MOVE", "BEFORE_PROPERTY_CREATE",
      "BEFORE_PROPERTY_DELETE", "AFTER_PROPERTY_CREATE", "AFTER_PROPERTY_DELETE",
    ], var.worker_action)
    error_message = "worker_action must be one of the actions supported by the jfrog/platform provider."
  }
}
