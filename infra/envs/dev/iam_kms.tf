# IAM policy for KMS key management (deletion)
data "aws_kms_alias" "main_key" {
  name = "alias/acme-main-key"
}

resource "aws_iam_policy" "kms_admin" {
  name        = "kms-admin-policy-dev"
  description = "Allow KMS key deletion for Terraform"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "kms:ScheduleKeyDeletion",
          "kms:CancelKeyDeletion",
          "kms:DescribeKey",
          "kms:GetKeyPolicy",
          "kms:ListAliases"
        ]
        Resource = data.aws_kms_alias.main_key.target_key_arn
      }
    ]
  })
}
