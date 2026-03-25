locals {
  jfrog_base_url = trimsuffix(var.jfrog_url, "/")

  worker_execute_url = (
    var.webhook_url != ""
    ? var.webhook_url
    : "${local.jfrog_base_url}/worker/api/v1/execute/${var.worker_key}"
  )
}
