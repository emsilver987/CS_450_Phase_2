variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "validator_service_url" { type = string }
variable "aws_region" {
  type    = string
  default = "us-east-1"
}
# Data sources
data "aws_caller_identity" "current" {}
data "aws_iam_role" "ecs_execution_role" {
  name = "ecs-execution-role"
}

# Main KMS Key for ACME project encryption
# This is the SINGLE managed key for all encryption needs
resource "aws_kms_key" "main" {
  description             = "Main KMS key for ACME project encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 7

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRoot"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${var.aws_region}.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:GenerateDataKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowCloudTrail"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey",
          "kms:Decrypt"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowSecretsManager"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:CreateGrant",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowECSExecutionRole"
        Effect = "Allow"
        Principal = {
          AWS = data.aws_iam_role.ecs_execution_role.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey",
          "kms:CreateGrant"
        ]
        Resource = "*"
      },
      {
        Sid    = "AllowGitHubActions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/github-actions-oidc-role"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:CreateGrant",
          "kms:PutKeyPolicy",
          "kms:UpdateAlias",
          "kms:CreateAlias",
          "kms:DeleteAlias",
          "kms:EnableKeyRotation",
          "kms:DisableKeyRotation",
          "kms:GetKeyRotationStatus",
          "kms:ScheduleKeyDeletion",
          "kms:CancelKeyDeletion"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name        = "acme-main-key"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
  }

  lifecycle {
    # Ignore policy changes to prevent Terraform from trying to update the key policy
    # The GitHub Actions OIDC role needs IAM permission (kms:PutKeyPolicy) to update
    # the key policy, which must be granted outside of Terraform.
    ignore_changes = [policy]
    # Note: prevent_destroy removed temporarily to allow resource migration
    # Re-enable after migration: prevent_destroy = true
  }
}

resource "aws_kms_alias" "main" {
  name          = "alias/acme-main-key"
  target_key_id = aws_kms_key.main.key_id
}

# Secrets Manager for JWT secret
resource "aws_secretsmanager_secret" "jwt_secret" {
  name = "acme-jwt-secret"

  kms_key_id = aws_kms_key.main.arn

  tags = {
    Name        = "acme-jwt-secret"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
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
  value = aws_kms_key.main.arn
}

output "kms_key_alias" {
  value = aws_kms_alias.main.name
}

output "jwt_secret_arn" {
  value = aws_secretsmanager_secret.jwt_secret.arn
}

output "dashboard_url" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=${aws_cloudwatch_dashboard.main_dashboard.dashboard_name}"
}
