resource "aws_s3_bucket" "artifacts" {
  bucket        = var.artifacts_name
  force_destroy = false
}

# Enable S3 versioning to protect against accidental overwrites and enable version recovery
resource "aws_s3_bucket_versioning" "this" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
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
    restrict_public_buckets  = true
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


