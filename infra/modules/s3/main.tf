resource "aws_s3_bucket" "artifacts" {
  bucket        = var.artifacts_name
  force_destroy = true
}

# KMS key for S3 bucket encryption
resource "aws_kms_key" "s3_encryption" {
  description             = "KMS key for S3 artifacts bucket encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name        = "s3-artifacts-encryption-key"
    Environment = var.environment
  }
}

resource "aws_kms_alias" "s3_encryption" {
  name          = "alias/s3-artifacts-encryption"
  target_key_id = aws_kms_key.s3_encryption.key_id
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3_encryption.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Access Point for secure access to the bucket
resource "aws_s3_access_point" "main" {
  name   = "cs450-s3"
  bucket = aws_s3_bucket.artifacts.id

  public_access_block_configuration {
    block_public_acls       = true
    block_public_policy     = true
    ignore_public_acls      = true
    restrict_public_buckets = true
  }

  lifecycle {
    # Prevent destruction of access point if bucket is being destroyed
    prevent_destroy = false
  }
}

output "artifacts_bucket" { value = aws_s3_bucket.artifacts.id }
output "access_point_arn" {
  value = aws_s3_access_point.main.arn
}


