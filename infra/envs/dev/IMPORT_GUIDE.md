# Terraform Resource Import Guide

## 🎯 Best Option: Import Existing Resources

Since your AWS resources already exist (created manually or from a previous Terraform run), the **best approach** is to **import them into Terraform state**. This way:

✅ Terraform will manage existing resources (no recreation)  
✅ No downtime or data loss  
✅ Future changes will be tracked properly  
✅ Safe and reversible

## 🚀 Quick Start

### Option 1: Use the Import Script (Recommended)

```bash
cd infra/envs/dev
./import-resources.sh
```

This script will automatically import all existing resources.

### Option 2: Manual Import

If you prefer to import manually, run these commands:

```bash
cd infra/envs/dev

# Initialize Terraform
terraform init

# Import Config module resources
terraform import module.config.aws_s3_bucket.config_snapshots pkg-artifacts-config-838693051036
terraform import module.config.aws_iam_role.config_role aws-config-role

# Import Monitoring module resources
terraform import module.monitoring.aws_s3_bucket.cloudtrail_logs pkg-artifacts-cloudtrail-logs-838693051036
terraform import module.monitoring.aws_cloudwatch_log_group.cloudtrail_logs /aws/cloudtrail/acme-audit-trail

# Import S3 module (if uncommented)
terraform import module.s3.aws_s3_bucket.artifacts pkg-artifacts
```

## 📋 After Import

1. **Verify the import:**

   ```bash
   terraform plan
   ```

   This should show minimal or no changes if resources match.

2. **If there are differences:**
   - Review the plan carefully
   - Terraform will show what needs to be updated
   - Most differences are likely tags or minor configs

3. **Apply changes:**
   ```bash
   terraform apply
   ```

## ⚠️ Important Notes

### KMS Key Issue

The CloudWatch Log Group KMS error can be resolved by:

1. **Ensure KMS key policy is updated first:**

   ```bash
   terraform apply -target=module.monitoring.aws_kms_key.main_key
   ```

2. **Then create/import the log group:**
   ```bash
   terraform import module.monitoring.aws_cloudwatch_log_group.cloudtrail_logs /aws/cloudtrail/acme-audit-trail
   ```

### If Resources Don't Match

If Terraform wants to replace resources after import:

1. **Check the resource configuration** in the module files
2. **Adjust Terraform config** to match existing resources (tags, settings, etc.)
3. **Or accept replacement** (only if safe - check for data loss!)

## 🔄 Alternative: Destroy and Recreate (NOT Recommended)

⚠️ **Only use if:**

- Resources are empty/test data
- You have backups
- You understand the risks

```bash
# Delete resources manually in AWS Console
# Then run terraform apply
```

## 📚 Resources to Import

Based on your errors, import these resources:

| Resource             | Import Command                                                                                                 |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| Config S3 Bucket     | `terraform import module.config.aws_s3_bucket.config_snapshots pkg-artifacts-config-838693051036`              |
| Config IAM Role      | `terraform import module.config.aws_iam_role.config_role aws-config-role`                                      |
| CloudTrail S3 Bucket | `terraform import module.monitoring.aws_s3_bucket.cloudtrail_logs pkg-artifacts-cloudtrail-logs-838693051036`  |
| CloudWatch Log Group | `terraform import module.monitoring.aws_cloudwatch_log_group.cloudtrail_logs /aws/cloudtrail/acme-audit-trail` |
| Main S3 Bucket       | `terraform import module.s3.aws_s3_bucket.artifacts pkg-artifacts`                                             |

## ✅ Verification

After import, verify everything is in sync:

```bash
terraform plan
# Should show: "No changes. Your infrastructure matches the configuration."
```

## 🆘 Troubleshooting

### "Resource already managed by Terraform"

- Resource is already imported, skip it

### "Resource not found"

- Resource doesn't exist in AWS, create it with `terraform apply`

### "Invalid resource address"

- Check the module path and resource name match your Terraform code

### KMS Permission Errors

- Update KMS key policy first: `terraform apply -target=module.monitoring.aws_kms_key.main_key`
- Wait a few seconds for policy propagation
- Then import/create the log group
