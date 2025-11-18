variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Docker image tag for the validator service"
}
variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS key used for Secrets Manager encryption"
}
