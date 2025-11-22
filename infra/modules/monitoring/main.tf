variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "validator_service_url" {
  type    = string
  default = ""
}

# KMS Key for encryption
resource "aws_kms_key" "main_key" {
  description             = "KMS key for ACME project encryption"
  deletion_window_in_days = 7

  tags = {
    Name        = "acme-main-key"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }

  lifecycle {
    ignore_changes = [policy]
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

# ============================================================================
# CloudTrail Audit Logging Configuration
# ============================================================================

# Get current AWS account ID and caller identity
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# S3 Bucket for CloudTrail logs
resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket = "${var.artifacts_bucket}-cloudtrail-logs-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "cloudtrail-logs"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
    Purpose     = "CloudTrail audit log storage"
  }
}

# Enable versioning on CloudTrail logs bucket
resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Block public access for CloudTrail logs bucket
resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Enable SSE-KMS encryption for CloudTrail logs bucket
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

# Lifecycle policy for CloudTrail logs - transition to Glacier after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    id     = "archive-cloudtrail-logs"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }
  }
}

# S3 bucket policy for CloudTrail
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
            "AWS:SourceArn" = "arn:aws:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/acme-audit-trail"
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
        Resource = "${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl"  = "bucket-owner-full-control"
            "AWS:SourceArn" = "arn:aws:cloudtrail:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:trail/acme-audit-trail"
          }
        }
      }
    ]
  })
}

# CloudTrail Trail
resource "aws_cloudtrail" "audit_trail" {
  name                          = "acme-audit-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_logging                = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.main_key.arn

  # S3 data events for artifacts bucket
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::${var.artifacts_bucket}/*"]
    }
  }

  # DynamoDB data events for all tables
  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::DynamoDB::Table"
      values = values(var.ddb_tables_arnmap)
    }
  }

  tags = {
    Name        = "acme-audit-trail"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
    Purpose     = "Multi-region audit trail with data event logging"
  }

  depends_on = [
    aws_s3_bucket_policy.cloudtrail_logs
  ]
}

output "cloudtrail_trail_arn" {
  description = "ARN of the CloudTrail audit trail"
  value       = aws_cloudtrail.audit_trail.arn
}

output "cloudtrail_logs_bucket" {
  description = "Name of the S3 bucket storing CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail_logs.id
}

output "cloudtrail_logs_bucket_arn" {
  description = "ARN of the S3 bucket storing CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail_logs.arn
}


