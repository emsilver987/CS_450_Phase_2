variable "artifacts_name" { type = string }
variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for SSE-KMS encryption"
}


