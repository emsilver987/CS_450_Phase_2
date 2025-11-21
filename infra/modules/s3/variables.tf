variable "artifacts_name" { type = string }
variable "environment" {
  type    = string
  default = "dev"
}
variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS key for S3 encryption. If not provided, will look up by alias 'alias/acme-main-key'"
  default     = ""
}



