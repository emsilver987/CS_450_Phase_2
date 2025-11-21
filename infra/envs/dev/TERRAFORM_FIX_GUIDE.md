# Terraform Deployment Fix Guide

## Issues and Solutions

### 1. KMS Key Deletion - AccessDeniedException

**Issue**: `deleting KMS Key: AccessDeniedException`

**Solution**: Attach the KMS admin policy to your IAM user/role:

```bash
# Get your current IAM user
aws sts get-caller-identity

# Attach the policy (replace USER_NAME with your IAM user)
aws iam attach-user-policy \
  --user-name USER_NAME \
  --policy-arn $(terraform output -raw kms_admin_policy_arn)
```

### 2. S3 Access Point - 409 Conflict

**Issue**: `Error creating S3 Access Point: StatusCode: 409`

**Solution**: Already fixed with `ignore_changes = [name]` in `modules/s3/main.tf`

If still failing, import the existing access point:

```bash
cd infra/envs/dev
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
