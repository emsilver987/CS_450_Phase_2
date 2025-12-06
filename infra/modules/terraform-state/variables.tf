variable "state_bucket_name" {
  type        = string
  description = "Name of the S3 bucket for Terraform state storage"
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for the state bucket"
}


