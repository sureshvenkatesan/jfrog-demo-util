# DML Worker Module: Block If Not Scanned

Optional Terraform module that deploys a JFrog Workers Service with a
`BEFORE_DOWNLOAD_REQUEST` action. The worker checks whether the requested
artifact has an `approved` property set to `"true"` and blocks the download
if it does not.

## Usage

```hcl
module "dml_worker" {
  source    = "./modules/dml-worker"
  repo_keys = ["my-generic-local"]
}
```

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| `worker_key` | Unique key for the worker | `string` | `"block-if-not-scanned"` | no |
| `enabled` | Whether the worker is enabled | `bool` | `true` | no |
| `description` | Human-readable description | `string` | *(see variables.tf)* | no |
| `repo_keys` | Repository keys the worker applies to | `list(string)` | — | **yes** |

## Outputs

| Name | Description |
|------|-------------|
| `worker_key` | Key of the deployed worker |

## Requirements

- Terraform >= 1.6
- JFrog Platform provider `~> 2.2`
- JFrog Enterprise X or Enterprise+ license (Workers Service requirement)
