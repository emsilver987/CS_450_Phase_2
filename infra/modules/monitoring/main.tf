variable "artifacts_bucket" { type = string }
variable "ddb_tables_arnmap" { type = map(string) }
variable "validator_service_url" { type = string }

# KMS Key for encryption
resource "aws_kms_key" "main_key" {
  description             = "KMS key for ACME project encryption"
  deletion_window_in_days = 7

  # Key policy to allow necessary principals to use the key
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::838693051036:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Secrets Manager to use the key"
        Effect = "Allow"
        Principal = {
          Service = "secretsmanager.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow GitHub Actions OIDC role to use and manage the key"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::838693051036:role/github-actions-oidc-role"
        }
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey",
          "kms:PutKeyPolicy"
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
    # Once the IAM permission is added, you can remove this lifecycle block to allow
    # Terraform to manage the key policy.
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
