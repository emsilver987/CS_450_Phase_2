resource "aws_s3_bucket" "artifacts" {
  bucket        = var.artifacts_name
  force_destroy = true
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

output "artifacts_bucket" { value = aws_s3_bucket.artifacts.id }


