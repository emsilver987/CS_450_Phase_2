variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "validator_service_url" { type = string }
variable "aws_account_id" {
  type        = string
  description = "AWS account ID"
}
variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for resource deployment"
}

# KMS Key for encryption
resource "aws_kms_key" "main_key" {
  description             = "KMS key for ACME project encryption"
  deletion_window_in_days = 7

  # Policy to allow CloudTrail and other services to use the key
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.aws_account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudTrail to encrypt logs"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = "arn:aws:cloudtrail:${var.aws_region}:${var.aws_account_id}:trail/acme-audit-trail"
          }
          StringLike = {
            "kms:EncryptionContext:aws:cloudtrail:arn" = "arn:aws:cloudtrail:${var.aws_region}:${var.aws_account_id}:trail/*"
          }
        }
      },
      {
        Sid    = "Allow CloudWatch Logs to decrypt"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          ArnEquals = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:${var.aws_region}:${var.aws_account_id}:*"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "acme-main-key"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

resource "aws_kms_alias" "main_key_alias" {
  name          = "alias/acme-main-key"
  target_key_id = aws_kms_key.main_key.key_id
}

# Secrets Manager for JWT secret
resource "aws_secretsmanager_secret" "jwt_secret" {
  name = "acme-jwt-secret"

  kms_key_id = aws_kms_key.main_key.arn

  tags = {
    Name        = "acme-jwt-secret"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }

  lifecycle {
    ignore_changes = [kms_key_id]
  }
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id = aws_secretsmanager_secret.jwt_secret.id
  secret_string = jsonencode({
    jwt_secret           = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm        = "HS256"
    jwt_expiration_hours = 10
    jwt_max_uses         = 1000
  })
}

# CloudWatch Alarms
resource "aws_cloudwatch_metric_alarm" "validator_high_cpu" {
  alarm_name          = "validator-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors validator service CPU utilization"

  dimensions = {
    ServiceName = "validator-service"
    ClusterName = "validator-cluster"
  }

  tags = {
    Name        = "validator-high-cpu"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

resource "aws_cloudwatch_metric_alarm" "validator_high_memory" {
  alarm_name          = "validator-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors validator service memory utilization"

  dimensions = {
    ServiceName = "validator-service"
    ClusterName = "validator-cluster"
  }

  tags = {
    Name        = "validator-high-memory"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

resource "aws_cloudwatch_metric_alarm" "validator_task_count" {
  alarm_name          = "validator-task-count"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "RunningTaskCount"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "1"
  alarm_description   = "This metric monitors validator service task count"

  dimensions = {
    ServiceName = "validator-service"
    ClusterName = "validator-cluster"
  }


  tags = {
    Name        = "validator-task-count"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

# CloudWatch Dashboard
resource "aws_cloudwatch_dashboard" "main_dashboard" {
  dashboard_name = "acme-main-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ServiceName", "validator-service", "ClusterName", "validator-cluster"],
            [".", "MemoryUtilization", ".", ".", ".", "."],
            [".", "RunningTaskCount", ".", ".", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "ECS Validator Service Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "packages"],
            [".", "ConsumedWriteCapacityUnits", ".", "."],
            [".", "ConsumedReadCapacityUnits", "TableName", "users"],
            [".", "ConsumedWriteCapacityUnits", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "DynamoDB Metrics"
          period  = 300
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/S3", "BucketSizeBytes", "BucketName", var.artifacts_bucket, "StorageType", "StandardStorage"],
            [".", "NumberOfObjects", ".", ".", ".", "."]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "S3 Bucket Metrics"
          period  = 300
        }
      }
    ]
  })
}

output "kms_key_arn" {
  value = aws_kms_key.main_key.arn
}

output "kms_key_alias" {
  value = aws_kms_alias.main_key_alias.name
}

output "jwt_secret_arn" {
  value = aws_secretsmanager_secret.jwt_secret.arn
}

output "dashboard_url" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=${aws_cloudwatch_dashboard.main_dashboard.dashboard_name}"
}

# CloudTrail S3 Bucket for audit logs
resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket        = "${var.artifacts_bucket}-cloudtrail-logs-${var.aws_account_id}"
  force_destroy = false # Prevent accidental deletion of audit logs

  tags = {
    Name        = "acme-cloudtrail-logs"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
    Purpose     = "CloudTrail audit logs"
  }
}

# Block public access to CloudTrail logs bucket
resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable versioning on CloudTrail logs bucket
resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Encrypt CloudTrail logs bucket with KMS
resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.main_key.arn
    }
    bucket_key_enabled = true
  }
}

# Lifecycle policy for CloudTrail logs (optional: move to Glacier after 90 days)
resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# CloudTrail bucket policy to allow CloudTrail service to write logs
resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail_logs.arn
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = "arn:aws:cloudtrail:${var.aws_region}:${var.aws_account_id}:trail/acme-audit-trail"
          }
        }
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudtrail_logs.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"    = "bucket-owner-full-control"
            "AWS:SourceArn"    = "arn:aws:cloudtrail:${var.aws_region}:${var.aws_account_id}:trail/acme-audit-trail"
            "aws:SourceAccount" = var.aws_account_id
          }
        }
      }
    ]
  })
}

# CloudTrail Trail - Explicit configuration for audit logging
resource "aws_cloudtrail" "audit_trail" {
  name                          = "acme-audit-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_logging                = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.main_key.arn

  # Include data events for S3 and DynamoDB
  event_selector {
    read_write_type                 = "All"
    include_management_events       = true
    exclude_management_event_sources = []

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::${var.artifacts_bucket}/*"]
    }
  }

  event_selector {
    read_write_type                 = "All"
    include_management_events       = true
    exclude_management_event_sources = []

    data_resource {
      type   = "AWS::DynamoDB::Table"
      values = values(var.ddb_tables_arnmap)
    }
  }

  tags = {
    Name        = "acme-audit-trail"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
    Purpose     = "Audit logging for compliance and security"
  }

  depends_on = [aws_s3_bucket_policy.cloudtrail_logs]
}

# CloudWatch Log Group for CloudTrail (optional: for CloudWatch Logs integration)
resource "aws_cloudwatch_log_group" "cloudtrail_logs" {
  name              = "/aws/cloudtrail/acme-audit-trail"
  retention_in_days = 90
  kms_key_id        = aws_kms_key.main_key.arn

  tags = {
    Name        = "cloudtrail-logs"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }
}

output "cloudtrail_trail_arn" {
  value       = aws_cloudtrail.audit_trail.arn
  description = "ARN of the CloudTrail audit trail"
}

output "cloudtrail_logs_bucket" {
  value       = aws_s3_bucket.cloudtrail_logs.id
  description = "S3 bucket name for CloudTrail logs"
}


