# AWS WAF Module - DoS Protection and Security Rules
# This module creates a WAF Web ACL with AWS Managed Rules and rate-based rules
# to protect against Denial of Service attacks and common web vulnerabilities

# WAF Web ACL
resource "aws_wafv2_web_acl" "main" {
  name        = "acme-waf-${var.environment}"
  description = "WAF Web ACL for ACME Registry - DoS Protection and Security Rules"
  scope       = "CLOUDFRONT" # Use CLOUDFRONT for CloudFront, REGIONAL for API Gateway/ALB

  default_action {
    allow {}
  }

  # Rule 1: AWS Managed Rules - Core Rule Set (OWASP Top 10)
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"

        # Exclude rules that might interfere with legitimate traffic
        rule_action_override {
          action_to_use {
            allow {}
          }
          name = "SizeRestrictions_BODY"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 2: AWS Managed Rules - Known Bad Inputs
  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "KnownBadInputsMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 3: AWS Managed Rules - Linux Operating System
  rule {
    name     = "AWSManagedRulesLinuxRuleSet"
    priority = 3

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesLinuxRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "LinuxRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 4: AWS Managed Rules - SQL Injection
  rule {
    name     = "AWSManagedRulesSQLiRuleSet"
    priority = 4

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLiRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 5: Rate-based rule for DoS protection
  rule {
    name     = "RateLimitRule"
    priority = 5

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitRuleMetric"
      sampled_requests_enabled   = true
    }
  }

  # Rule 6: Size restrictions - Block oversized requests
  rule {
    name     = "SizeRestrictionsRule"
    priority = 6

    action {
      block {}
    }

    statement {
      or_statement {
        statement {
          size_constraint_statement {
            field_to_match {
              body {}
            }
            comparison_operator = "GT"
            size                = 10485760 # 10 MB
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
        statement {
          size_constraint_statement {
            field_to_match {
              uri_path {}
            }
            comparison_operator = "GT"
            size                = 8192 # 8 KB
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
        statement {
          size_constraint_statement {
            field_to_match {
              query_string {}
            }
            comparison_operator = "GT"
            size                = 8192 # 8 KB
            text_transformation {
              priority = 0
              type     = "NONE"
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SizeRestrictionsMetric"
      sampled_requests_enabled   = true
    }
  }

  # Visibility and logging configuration
  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "ACMEWAFMetric"
    sampled_requests_enabled   = true
  }

  tags = {
    Name        = "acme-waf-${var.environment}"
    Environment = var.environment
    Project     = "CS_450_Phase_2"
  }
}

# S3 Bucket for WAF logs (CloudFront WAF requires S3 or Kinesis, not CloudWatch Logs)
resource "aws_s3_bucket" "waf_logs" {
  bucket = "acme-waf-logs-${var.environment}-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name        = "acme-waf-logs-${var.environment}"
    Environment = var.environment
    Project     = "CS_450_Phase_2"
  }
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 Bucket Public Access Block
resource "aws_s3_bucket_public_access_block" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# S3 Bucket Lifecycle - Transition to Glacier after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "waf_logs" {
  bucket = aws_s3_bucket.waf_logs.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
  }
}

# IAM Policy for WAF to write to S3
data "aws_iam_policy_document" "waf_logging_policy" {
  statement {
    sid    = "AllowWAFLogging"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }

    actions = [
      "s3:PutObject"
    ]

    resources = ["${aws_s3_bucket.waf_logs.arn}/*"]
  }

  statement {
    sid    = "AllowWAFLoggingBucketAccess"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["delivery.logs.amazonaws.com"]
    }

    actions = [
      "s3:GetBucketAcl"
    ]

    resources = [aws_s3_bucket.waf_logs.arn]
  }
}

resource "aws_s3_bucket_policy" "waf_logging" {
  bucket = aws_s3_bucket.waf_logs.id
  policy = data.aws_iam_policy_document.waf_logging_policy.json
}

# WAF Logging Configuration - Use S3 for CloudFront WAF
resource "aws_wafv2_web_acl_logging_configuration" "main" {
  resource_arn            = aws_wafv2_web_acl.main.arn
  log_destination_configs = ["arn:aws:s3:::${aws_s3_bucket.waf_logs.bucket}/waf-logs/"]

  depends_on = [aws_s3_bucket_policy.waf_logging]
}

# Outputs
output "web_acl_id" {
  value       = aws_wafv2_web_acl.main.id
  description = "WAF Web ACL ID"
}

output "web_acl_arn" {
  value       = aws_wafv2_web_acl.main.arn
  description = "WAF Web ACL ARN"
}

output "web_acl_name" {
  value       = aws_wafv2_web_acl.main.name
  description = "WAF Web ACL Name"
}

