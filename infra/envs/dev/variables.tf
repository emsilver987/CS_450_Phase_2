variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for resource deployment"
}

variable "artifacts_bucket" {
  type    = string
  default = "pkg-artifacts"
}
variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Docker image tag for the validator service"
}
variable "aws_account_id" {
  type        = string
  description = "AWS account ID"
  default     = "838693051036"
}
variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for encryption (optional, will look up via alias if not provided)"
  default     = ""
}
variable "github_token" {
  type        = string
  description = "GitHub Personal Access Token for API requests"
  default     = "ghp_test_token_placeholder"
  sensitive   = true
}
