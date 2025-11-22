# Terraform Initialization Fix - Summary

## Problem Identified

The Terraform initialization was failing with "Process completed with exit code 3" due to a **circular dependency** between modules:

### Root Cause
1. **S3 Module** (`infra/modules/s3/main.tf`) was using a `data` source to look up the KMS key alias `alias/acme-main-key`
2. **KMS Key** is created in the **Monitoring Module** (`infra/modules/monitoring/main.tf`)
3. During the **first Terraform run**, the KMS key doesn't exist yet, so the S3 module's data lookup fails during the `terraform init` phase
4. This caused Terraform to fail before it could even create the KMS key

### Dependency Chain Issue
```
S3 Module (data lookup) → KMS Key Alias → Monitoring Module (creates KMS)
                ↑                                    ↓
                └────────── Circular Dependency ─────┘
```

## Solution Implemented

### 1. **Reordered Module Dependencies** (`infra/envs/dev/main.tf`)
- Moved the **Monitoring Module** to be created **before** the S3 module
- This ensures the KMS key exists before S3 tries to use it
- Passed the KMS key ARN directly from monitoring to S3 module

**Before:**
```hcl
module "s3" {
  source         = "../../modules/s3"
  artifacts_name = local.artifacts_bucket
  environment    = "dev"
}

module "monitoring" {
  source                = "../../modules/monitoring"
  artifacts_bucket      = local.artifacts_bucket
  ddb_tables_arnmap     = local.ddb_tables_arnmap
  validator_service_url = module.ecs.validator_service_url
}
```

**After:**
```hcl
# Create monitoring module first to ensure KMS key exists
module "monitoring" {
  source            = "../../modules/monitoring"
  artifacts_bucket  = local.artifacts_bucket
  ddb_tables_arnmap = local.ddb_tables_arnmap
}

# S3 module now receives KMS key ARN from monitoring module
module "s3" {
  source         = "../../modules/s3"
  artifacts_name = local.artifacts_bucket
  environment    = "dev"
  kms_key_arn    = module.monitoring.kms_key_arn
}
```

### 2. **Removed Data Source Lookup** (`infra/modules/s3/main.tf`)
- Removed the `data "aws_kms_alias"` lookup that was causing the circular dependency
- S3 module now receives the KMS key ARN as a required parameter

**Removed:**
```hcl
data "aws_kms_alias" "main_key" {
  count = var.kms_key_arn == "" ? 1 : 0
  name  = "alias/acme-main-key"
}

locals {
  kms_key_id = var.kms_key_arn != "" ? var.kms_key_arn : data.aws_kms_alias.main_key[0].target_key_arn
}
```

**Replaced with:**
```hcl
# KMS key ARN is provided as a variable from the monitoring module
# This ensures proper dependency ordering and avoids circular dependencies
```

### 3. **Made validator_service_url Optional** (`infra/modules/monitoring/main.tf`)
- The monitoring module was requiring `validator_service_url` from the ECS module
- Since this variable isn't actually used in any monitoring resources, made it optional
- This allows monitoring to be created before ECS

**Before:**
```hcl
variable "validator_service_url" { type = string }
```

**After:**
```hcl
variable "validator_service_url" { 
  type    = string 
  default = ""
}
```

### 4. **Updated S3 Module Variables** (`infra/modules/s3/variables.tf`)
- Made `kms_key_arn` a required parameter (removed default value)
- Updated description to reflect that it's provided by the monitoring module

## Files Modified

1. **`infra/envs/dev/main.tf`**
   - Reordered modules: monitoring → iam → s3 → ecs
   - Added `kms_key_arn` parameter to S3 module call

2. **`infra/modules/s3/main.tf`**
   - Removed data source lookup for KMS key
   - Updated encryption configuration to use `var.kms_key_arn` directly

3. **`infra/modules/s3/variables.tf`**
   - Made `kms_key_arn` required
   - Updated description

4. **`infra/modules/monitoring/main.tf`**
   - Made `validator_service_url` optional with default value

## Expected Outcome

✅ **Terraform init** will now succeed because:
- The KMS key is created in the monitoring module first
- The S3 module receives the KMS key ARN as a parameter (no data lookup)
- No circular dependencies exist

✅ **Proper dependency chain:**
```
DDB Module → Monitoring Module (creates KMS) → S3 Module (uses KMS) → ECS Module
```

## Testing Recommendations

1. **Clear Terraform state** (if testing locally):
   ```bash
   cd infra/envs/dev
   rm -rf .terraform
   rm .terraform.lock.hcl
   ```

2. **Run Terraform init**:
   ```bash
   terraform init
   ```

3. **Verify plan**:
   ```bash
   terraform plan -var="aws_region=us-east-1" -var="aws_account_id=838693051036" -var="image_tag=test"
   ```

4. **Push to GitHub** to trigger the CD workflow and verify it completes successfully

## Additional Notes

- The workflow already has good error handling for S3 bucket creation with proper LocationConstraint handling for us-east-1
- The workflow includes retry logic for Terraform init with checksum mismatch handling
- DynamoDB lock cleanup is handled in the workflow
- All existing bucket creation and verification logic remains intact
