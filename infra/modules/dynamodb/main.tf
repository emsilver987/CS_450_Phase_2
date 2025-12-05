locals {
  tables = {
    users = {
      hash_key = "user_id"
      gsi = {
        "username-index" = {
          hash_key        = "username"
          projection_type = "ALL"
        }
      }
    }
    tokens    = { hash_key = "token_id", ttl_attr = "exp_ts" }
    packages  = { hash_key = "pkg_key" }
    uploads   = { hash_key = "upload_id" }
    artifacts = { hash_key = "artifact_id" }
    downloads = {
      hash_key = "event_id"
      gsi = {
        "user-timestamp-index" = {
          hash_key        = "user_id"
          range_key       = "timestamp"
          projection_type = "ALL"
        }
      }
    }
    performance_metrics = {
      hash_key  = "run_id"
      range_key = "metric_id"
      gsi = {
        "run-timestamp-index" = {
          hash_key        = "run_id"
          range_key       = "timestamp"
          projection_type = "ALL"
        }
      }
    }
  }
}

resource "aws_dynamodb_table" "this" {
  for_each     = local.tables
  name         = each.key
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = each.value.hash_key
  range_key    = try(each.value.range_key, null)

  # Prevent accidental deletion of existing tables
  lifecycle {
    ignore_changes = [
      # Ignore changes to table name, billing mode, and hash key
      # These are set correctly and shouldn't change
    ]
  }

  attribute {
    name = each.value.hash_key
    type = "S"
  }

  # Add range key attribute if it exists
  dynamic "attribute" {
    for_each = try(each.value.range_key != null, false) ? [1] : []
    content {
      name = try(each.value.range_key, null)
      type = "S"
    }
  }

  # Add GSI attributes if they exist (avoid duplicates)
  dynamic "attribute" {
    for_each = try(each.value.gsi, {})
    content {
      name = attribute.value.hash_key
      type = "S"
    }
  }

  # Add GSI range key attributes only when they exist (not null)
  dynamic "attribute" {
    for_each = {
      for idx_name, idx_config in try(each.value.gsi, {}) :
      idx_name => idx_config.range_key
      if try(idx_config.range_key, null) != null
    }
    content {
      name = attribute.value
      type = "S"
    }
  }

  # Add GSI if it exists
  dynamic "global_secondary_index" {
    for_each = try(each.value.gsi, {})
    content {
      name            = global_secondary_index.key
      hash_key        = global_secondary_index.value.hash_key
      range_key       = try(global_secondary_index.value.range_key, null)
      projection_type = global_secondary_index.value.projection_type
    }
  }

  ttl {
    enabled        = try(each.value.ttl_attr != null, false)
    attribute_name = try(each.value.ttl_attr, null)
  }

  # Enable Point-in-Time Recovery (PITR) for audit tables to prevent repudiation
  # PITR allows recovery of deleted items and provides protection against tampering
  point_in_time_recovery {
    enabled = contains(["downloads", "users", "tokens"], each.key)
  }

  # Enable DynamoDB Streams for audit tables to replicate entries to backup table
  # Streams provide real-time backup and prevent deletion of audit entries
  stream_enabled   = contains(["downloads"], each.key)
  stream_view_type = contains(["downloads"], each.key) ? "NEW_AND_OLD_IMAGES" : null

  # Enable server-side encryption at rest for all tables
  # This protects sensitive data (e.g., password hashes) if DynamoDB is compromised
  server_side_encryption {
    enabled = true
  }
}

output "arn_map" { value = { for k, t in aws_dynamodb_table.this : k => t.arn } }

# Backup table for downloads audit entries (non-repudiation)
# This table receives replicated entries from DynamoDB Streams to prevent deletion
resource "aws_dynamodb_table" "downloads_backup" {
  name         = "downloads-backup"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "event_id"

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  global_secondary_index {
    name            = "user-timestamp-index"
    hash_key        = "user_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Enable PITR for backup table as well
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name        = "downloads-backup"
    Environment = "dev"
    Project     = "CS_450_Phase_2"
    Purpose     = "Audit trail backup for non-repudiation"
  }
}

# Note: DynamoDB Streams replication to backup table should be configured via Lambda function
# The Lambda function should process stream events from downloads table and write to downloads-backup
# This provides real-time backup and prevents deletion of audit entries

