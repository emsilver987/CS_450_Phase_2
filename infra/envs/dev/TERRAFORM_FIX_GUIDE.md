# Terraform Deployment Fix Guide

## Issues and Solutions

### 1. KMS Key Policy Update - AccessDeniedException

**Issue**: `updating KMS Key policy: AccessDeniedException`

**Solution**: Removed inline policy from KMS key resource and added `lifecycle { ignore_changes = [policy] }` to prevent Terraform from updating the policy. KMS key policy should be managed manually or through IAM, not Terraform.

### 2. S3 Access Point - 409 Conflict

**Issue**: `Error creating S3 Access Point: StatusCode: 409`

**Solution**: Import the existing access point:

```bash
cd infra/envs/dev
./import-s3-access-point.sh
```

Or manually:
```bash
terraform import module.s3.aws_s3_access_point.main pkg-artifacts:cs450-s3
```

### 3. Provider Region Mismatch

**Issue**: Import errors due to region mismatch

**Solution**: Ensure provider region matches deployed resources:

```bash
# Check current region
aws configure get region

# Set region in variables.tf or use environment variable
export AWS_REGION=us-east-1
```

### 4. Module "ddb" Not Found

**Issue**: `ERROR: module.ddb not found in configuration!`

**Solution**: Already defined in `main.tf`. If error persists:

```bash
cd infra/envs/dev
terraform init -upgrade
terraform validate
```

## Quick Fix Commands

```bash
# 1. Initialize and validate
cd infra/envs/dev
terraform init -upgrade
terraform validate

# 2. Import existing resources (if needed)
./import-resources.sh

# 3. Plan and apply
terraform plan -out=tfplan
terraform apply tfplan
```

## Prevention

Add this output to `main.tf` to track the KMS policy:

```hcl
output "kms_admin_policy_arn" { 
  value = aws_iam_policy.kms_admin.arn 
}
```
