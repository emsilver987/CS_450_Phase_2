variable "artifacts_name" { type = string }
variable "environment" {
  type    = string
  default = "dev"
}
variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS key for S3 encryption (provided by monitoring module)"
}



