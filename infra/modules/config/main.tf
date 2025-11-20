variable "aws_region" {
  type        = string
  description = "AWS region for resource deployment"
}

variable "config_bucket_name" {
  type        = string
  description = "Name of the S3 bucket for AWS Config snapshots"
}

variable "kms_key_arn" {
  type        = string
  description = "ARN of the KMS key for encryption"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to resources"
  default     = {}
}

# S3 Bucket for AWS Config snapshots
resource "aws_s3_bucket" "config_snapshots" {
  bucket        = var.config_bucket_name
  force_destroy = false # Prevent accidental deletion of config snapshots

  tags = merge(
    var.tags,
    {
      Name    = "acme-config-snapshots"
      Purpose = "AWS Config snapshots"
    }
  )
}

# Block public access to Config snapshots bucket
resource "aws_s3_bucket_public_access_block" "config_snapshots" {
  bucket = aws_s3_bucket.config_snapshots.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning on Config snapshots bucket
resource "aws_s3_bucket_versioning" "config_snapshots" {
  bucket = aws_s3_bucket.config_snapshots.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Encrypt Config snapshots bucket with KMS
resource "aws_s3_bucket_server_side_encryption_configuration" "config_snapshots" {
  bucket = aws_s3_bucket.config_snapshots.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

# Lifecycle policy for Config snapshots (optional: move to Glacier after 90 days)
resource "aws_s3_bucket_lifecycle_configuration" "config_snapshots" {
  bucket = aws_s3_bucket.config_snapshots.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# IAM Role for AWS Config
resource "aws_iam_role" "config_role" {
  name = "aws-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name    = "aws-config-role"
      Purpose = "IAM role for AWS Config service"
    }
  )
}

# IAM Policy for AWS Config to deliver snapshots to S3
resource "aws_iam_role_policy" "config_role_policy" {
  name = "aws-config-role-policy"
  role = aws_iam_role.config_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetBucketAcl"
        ]
        Resource = [
          "${aws_s3_bucket.config_snapshots.arn}/*",
          aws_s3_bucket.config_snapshots.arn
        ]
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect = "Allow"
        Action = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.config_snapshots.arn
      }
    ]
  })
}

# Attach AWS managed policy for Config service
resource "aws_iam_role_policy_attachment" "config_role_policy" {
  role       = aws_iam_role.config_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

# AWS Config Delivery Channel
# Note: Delivery channel must be created before the recorder
resource "aws_config_delivery_channel" "config_delivery" {
  name           = "aws-config-delivery-channel"
  s3_bucket_name = aws_s3_bucket.config_snapshots.id
  s3_key_prefix  = "config-snapshots"

  snapshot_delivery_properties {
    delivery_frequency = "TwentyFour_Hours"
  }

  # No dependency on recorder - this creates a cycle
  # The delivery channel can exist independently
}

# AWS Config Configuration Recorder
resource "aws_config_configuration_recorder" "config_recorder" {
  name     = "aws-config-recorder"
  role_arn = aws_iam_role.config_role.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }

  # Recorder should depend on delivery channel being ready
  depends_on = [
    aws_config_delivery_channel.config_delivery
  ]
}

# Start the Config recorder
# This must be created after both the recorder and delivery channel exist
resource "aws_config_configuration_recorder_status" "config_recorder" {
  name       = aws_config_configuration_recorder.config_recorder.name
  is_enabled = true
  
  depends_on = [
    aws_config_configuration_recorder.config_recorder,
    aws_config_delivery_channel.config_delivery
  ]
}

output "config_bucket_name" {
  value       = aws_s3_bucket.config_snapshots.id
  description = "Name of the S3 bucket for AWS Config snapshots"
}

output "config_recorder_name" {
  value       = aws_config_configuration_recorder.config_recorder.name
  description = "Name of the AWS Config recorder"
}

output "config_role_arn" {
  value       = aws_iam_role.config_role.arn
  description = "ARN of the IAM role for AWS Config"
}
