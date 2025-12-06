# Terraform State Bucket Configuration
# This module manages the S3 bucket used for Terraform state storage
# with encryption, versioning, and IAM access restrictions to prevent
# unauthorized modification of IAM policies via Terraform state manipulation

resource "aws_s3_bucket" "terraform_state" {
  bucket = var.state_bucket_name
  # Prevent accidental deletion
  force_destroy = false

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name        = "terraform-state-bucket"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
    Purpose     = "Terraform state storage"
  }
}

# Enable versioning to track all state file changes
# This prevents unauthorized modifications by maintaining history
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption for state files
# This protects sensitive data (IAM policies, secrets) in state files
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = false
  }
}

# Block public access to state bucket
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# IAM policy to restrict access to Terraform state bucket
# Only specific IAM users/roles should have access to prevent unauthorized modifications
resource "aws_iam_policy" "terraform_state_access" {
  name        = "terraform-state-bucket-access"
  description = "Restrict access to Terraform state bucket to prevent unauthorized IAM policy modifications"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.terraform_state.arn,
          "${aws_s3_bucket.terraform_state.arn}/*"
        ]
        # Condition: Only allow access from specific IAM roles/users
        # This should be customized based on your team's IAM structure
        Condition = {
          StringEquals = {
            "aws:PrincipalTag/Project" = "CS_450_Phase_2"
          }
        }
      }
    ]
  })
}

output "state_bucket_name" {
  value       = aws_s3_bucket.terraform_state.id
  description = "Name of the Terraform state bucket"
}

output "state_bucket_arn" {
  value       = aws_s3_bucket.terraform_state.arn
  description = "ARN of the Terraform state bucket"
}

