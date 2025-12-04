variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for S3 encryption"
}
variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Docker image tag for the validator service"
}
variable "github_token_secret_arn" {
  type        = string
  description = "ARN of the GitHub token secret in Secrets Manager"
}
variable "jwt_secret_arn" {
  type        = string
  description = "ARN of the JWT secret in Secrets Manager"
}
variable "storage_backend" {
  type        = string
  default     = "s3"
  description = "Storage backend to use: 's3' or 'rds'"
}
variable "rds_endpoint" {
  type        = string
  default     = ""
  description = "RDS endpoint (hostname only, without port)"
}
variable "rds_database" {
  type        = string
  default     = "acme"
  description = "RDS database name"
}
variable "rds_username" {
  type        = string
  default     = "acme"
  description = "RDS username"
}
variable "rds_password" {
  type        = string
  default     = ""
  sensitive   = true
  description = "RDS password"
}
