variable "aws_region" {
  type        = string
  description = "AWS region for AWS Config resources"
}

variable "config_bucket_name" {
  type        = string
  description = "Name of the S3 bucket for AWS Config snapshots"
}

variable "kms_key_arn" {
  type        = string
  description = "KMS key ARN for encrypting Config snapshots"
}

variable "tags" {
  type        = map(string)
  default     = {}
  description = "Tags to apply to AWS Config resources"
}

# S3 bucket for AWS Config snapshots
resource "aws_s3_bucket" "config_snapshots" {
  bucket = var.config_bucket_name

  tags = merge(
    var.tags,
    {
      Name        = "aws-config-snapshots"
      Environment = "dev"
      Project     = "CS_450_Phase_2"
    }
  )
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "config_snapshots" {
  bucket = aws_s3_bucket.config_snapshots.id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 bucket encryption
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

# S3 bucket public access block
resource "aws_s3_bucket_public_access_block" "config_snapshots" {
  bucket = aws_s3_bucket.config_snapshots.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 bucket policy for AWS Config
resource "aws_s3_bucket_policy" "config_snapshots" {
  bucket = aws_s3_bucket.config_snapshots.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSConfigBucketPermissionsCheck"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.config_snapshots.arn
        Condition = {
          StringEquals = {
            "AWS:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid    = "AWSConfigBucketExistenceCheck"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.config_snapshots.arn
        Condition = {
          StringEquals = {
            "AWS:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      },
      {
        Sid    = "AWSConfigBucketDelivery"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.config_snapshots.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"     = "bucket-owner-full-control"
            "AWS:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# IAM role for AWS Config
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
        Condition = {
          StringEquals = {
            "AWS:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = merge(
    var.tags,
    {
      Name        = "aws-config-role"
      Environment = "dev"
      Project     = "CS_450_Phase_2"
    }
  )
}

# IAM policy for AWS Config
resource "aws_iam_role_policy" "config_policy" {
  name = "aws-config-policy"
  role = aws_iam_role.config_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.config_snapshots.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetBucketAcl"
        ]
        Resource = aws_s3_bucket.config_snapshots.arn
      },
      {
        Effect = "Allow"
        Action = [
          "config:Put*"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach AWS managed policy for Config
resource "aws_iam_role_policy_attachment" "config_policy" {
  role       = aws_iam_role.config_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

# SNS topic for AWS Config notifications
resource "aws_sns_topic" "config_notifications" {
  name              = "aws-config-notifications"
  kms_master_key_id = var.kms_key_arn

  tags = merge(
    var.tags,
    {
      Name        = "aws-config-notifications"
      Environment = "dev"
      Project     = "CS_450_Phase_2"
    }
  )
}

# AWS Config Configuration Recorder
resource "aws_config_configuration_recorder" "main" {
  name     = "aws-config-recorder"
  role_arn = aws_iam_role.config_role.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }

  depends_on = [
    aws_iam_role.config_role
  ]
}

# AWS Config Delivery Channel
resource "aws_config_delivery_channel" "main" {
  name           = "aws-config-delivery-channel"
  s3_bucket_name = aws_s3_bucket.config_snapshots.bucket
  sns_topic_arn  = aws_sns_topic.config_notifications.arn

  snapshot_delivery_properties {
    delivery_frequency = "TwentyFour_Hours"
  }

  depends_on = [
    aws_config_configuration_recorder.main,
    aws_s3_bucket_policy.config_snapshots
  ]
}

# Start the Configuration Recorder
resource "aws_config_configuration_recorder_status" "main" {
  name       = aws_config_configuration_recorder.main.name
  is_enabled = true

  depends_on = [
    aws_config_delivery_channel.main
  ]
}

# Outputs
output "config_bucket_name" {
  value       = aws_s3_bucket.config_snapshots.bucket
  description = "Name of the S3 bucket storing AWS Config snapshots"
}

output "config_bucket_arn" {
  value       = aws_s3_bucket.config_snapshots.arn
  description = "ARN of the S3 bucket storing AWS Config snapshots"
}

output "config_role_arn" {
  value       = aws_iam_role.config_role.arn
  description = "ARN of the IAM role used by AWS Config"
}

output "config_recorder_name" {
  value       = aws_config_configuration_recorder.main.name
  description = "Name of the AWS Config Configuration Recorder"
}

output "sns_topic_arn" {
  value       = aws_sns_topic.config_notifications.arn
  description = "ARN of the SNS topic for AWS Config notifications"
}

