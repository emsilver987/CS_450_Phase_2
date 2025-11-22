# Terraform Deployment Troubleshooting Guide

## Quick Diagnosis Steps

If the GitHub Actions CD workflow fails, follow these steps:

### 1. Check the Error Type

Look at the workflow logs to identify the error:

#### **Error: "Process completed with exit code 3"**
- **Cause**: Terraform init failed
- **Solution**: Check for circular dependencies or missing resources
- **Status**: ✅ **FIXED** - Circular dependency between S3 and KMS modules resolved

#### **Error: "Checksum mismatch"**
- **Cause**: S3 eventual consistency issue
- **Solution**: Workflow automatically retries with `-reconfigure` flag
- **Manual fix**:
  ```bash
  cd infra/envs/dev
  terraform init -reconfigure -input=false
  ```

#### **Error: "State lock"**
- **Cause**: Stale DynamoDB lock from previous failed run
- **Solution**: Clear stale locks
  ```bash
  # List locks
  aws dynamodb scan --table-name terraform-state-lock --region us-east-1
  
  # Delete specific lock (replace LOCK_ID)
  aws dynamodb delete-item \
    --table-name terraform-state-lock \
    --key '{"LockID":{"S":"LOCK_ID"}}' \
    --region us-east-1
  ```

#### **Error: "Backend bucket not found"**
- **Cause**: S3 backend bucket doesn't exist
- **Solution**: Workflow automatically creates it, but you can verify:
  ```bash
  # Check if bucket exists
  aws s3api head-bucket --bucket pkg-artifacts --region us-east-1
  
  # Create if missing
  aws s3api create-bucket --bucket pkg-artifacts --region us-east-1
  aws s3api put-bucket-versioning \
    --bucket pkg-artifacts \
    --versioning-configuration Status=Enabled
  ```

### 2. Verify AWS Credentials

Ensure OIDC role has proper permissions:

```bash
# Verify identity
aws sts get-caller-identity

# Check role ARN
# Should be: arn:aws:iam::838693051036:role/github-actions-oidc-role
```

### 3. Check Module Dependencies

The correct module order is:
```
1. DynamoDB (ddb)
2. Monitoring (creates KMS key)
3. IAM
4. S3 (uses KMS key from monitoring)
5. ECS
6. WAF
7. CloudFront
8. API Gateway
```

### 4. Validate Terraform Configuration Locally

```bash
cd infra/envs/dev

# Initialize
terraform init

# Validate syntax
terraform validate

# Check formatting
terraform fmt -check -recursive

# Plan (requires AWS credentials)
terraform plan \
  -var="aws_region=us-east-1" \
  -var="aws_account_id=838693051036" \
  -var="image_tag=test"
```

## Common Issues and Solutions

### Issue: "KMS key not found"
**Status**: ✅ **FIXED**

**Previous Error**:
```
Error: error reading KMS Alias (alias/acme-main-key): AliasNotFoundException
```

**Solution Applied**:
- Reordered modules so monitoring (which creates KMS) runs before S3
- S3 module now receives KMS ARN as parameter instead of looking it up

### Issue: "Bucket already exists but not in state"
**Solution**: Import the bucket
```bash
cd infra/envs/dev
terraform import \
  -var="aws_region=us-east-1" \
  -var="aws_account_id=838693051036" \
  module.s3.aws_s3_bucket.artifacts \
  pkg-artifacts
```

### Issue: "Access point already exists"
**Solution**: Import the access point
```bash
cd infra/envs/dev
terraform import \
  -var="aws_region=us-east-1" \
  -var="aws_account_id=838693051036" \
  module.s3.aws_s3_access_point.main \
  arn:aws:s3:us-east-1:838693051036:accesspoint/cs450-s3
```

### Issue: "DynamoDB table already exists"
**Solution**: Workflow automatically imports tables
- The workflow has import steps for all DynamoDB tables
- If import fails, manually import:
```bash
cd infra/envs/dev
terraform import \
  -var="aws_region=us-east-1" \
  -var="aws_account_id=838693051036" \
  'module.ddb.aws_dynamodb_table.this["packages"]' \
  packages
```

## Workflow Steps Explained

### Step 1: Ensure Backend Resources
- Creates `pkg-artifacts` S3 bucket if it doesn't exist
- Creates `terraform-state-lock` DynamoDB table if it doesn't exist
- Handles us-east-1 LocationConstraint correctly

### Step 2: Clean Stale Locks
- Scans DynamoDB for locks older than 1 hour
- Logs stale locks but doesn't delete them (Terraform handles cleanup)

### Step 3: Terraform Init
- Attempts init up to 3 times
- Handles checksum mismatches with `-reconfigure`
- Waits for S3 eventual consistency (20 seconds)
- Provides detailed error messages

### Step 4: Import Existing Resources
- Imports S3 bucket if it exists
- Imports S3 access point if it exists
- Imports all DynamoDB tables if they exist
- All import steps use `continue-on-error: true`

### Step 5: Cleanup Orphaned Resources
- Removes old Config and CloudTrail resources from state
- Removes old S3 KMS key from state (key remains in AWS)

## Manual Recovery Steps

If the workflow is completely stuck:

### 1. Clear Local Terraform State (if testing locally)
```bash
cd infra/envs/dev
rm -rf .terraform
rm .terraform.lock.hcl
```

### 2. Clear Remote State Lock
```bash
# List all locks
aws dynamodb scan --table-name terraform-state-lock --region us-east-1

# Delete all locks (CAUTION: only if no other runs are active)
aws dynamodb scan --table-name terraform-state-lock --region us-east-1 \
  --query 'Items[*].LockID.S' --output text | \
  xargs -I {} aws dynamodb delete-item \
    --table-name terraform-state-lock \
    --key '{"LockID":{"S":"{}"}}' \
    --region us-east-1
```

### 3. Force Unlock (last resort)
```bash
cd infra/envs/dev
terraform force-unlock LOCK_ID
```

## Monitoring Deployment

### Check ECS Service Status
```bash
aws ecs describe-services \
  --cluster validator-cluster \
  --services validator-service \
  --region us-east-1
```

### Check Task Status
```bash
aws ecs list-tasks \
  --cluster validator-cluster \
  --service-name validator-service \
  --region us-east-1

# Get task details
aws ecs describe-tasks \
  --cluster validator-cluster \
  --tasks TASK_ARN \
  --region us-east-1
```

### Check Logs
```bash
aws logs tail /ecs/validator-service --follow --region us-east-1
```

## Contact Information

If issues persist:
1. Check the `TERRAFORM_FIX_SUMMARY.md` for detailed fix information
2. Review GitHub Actions workflow logs
3. Check AWS CloudWatch logs for runtime errors
4. Verify all AWS resources are in the correct region (us-east-1)

## Recent Fixes Applied

✅ **2025-11-21**: Fixed circular dependency between S3 and KMS modules
- Reordered module creation: monitoring → s3
- Removed data source lookup in S3 module
- Made validator_service_url optional in monitoring module
- Made kms_key_arn required parameter in S3 module
