variable "aws_region" {
  description = "AWS region for RDS instance"
  type        = string
  default     = "us-east-1"
}

variable "db_name" {
  description = "Database name"
  type        = string
  default     = "acme"
}

variable "db_username" {
  description = "Database master username"
  type        = string
  default     = "acme"
}

variable "db_password" {
  description = "Database master password"
  type        = string
  sensitive   = true
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "vpc_id" {
  description = "VPC ID where RDS will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for RDS subnet group"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs to allow access to RDS"
  type        = list(string)
  default     = []
}

