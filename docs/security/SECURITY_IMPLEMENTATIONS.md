# Security Implementations Guide

This document details the security features implemented in the CS_450_Phase_2 project, including SHA-256 hash verification, S3 SSE-KMS encryption, and Terraform configuration.

## Table of Contents

1. [SHA-256 Hash Verification](#sha-256-hash-verification)
2. [S3 SSE-KMS Encryption](#s3-sse-kms-encryption)
3. [Terraform Configuration](#terraform-configuration)

---

## SHA-256 Hash Verification

### Overview

SHA-256 hash verification ensures package integrity by computing a hash during upload and verifying it during download. This prevents tampering and ensures data integrity throughout the package lifecycle.

### Implementation Details

#### Upload Process

**Location:** `src/services/s3_service.py` and `src/services/package_service.py`

1. **Simple Upload (`upload_model` function):**
   - Computes SHA-256 hash of file content before upload
   - Returns hash in response: `{"message": "Upload successful", "sha256_hash": "..."}`
   - Hash is logged for audit purposes

2. **Multipart Upload (`commit_upload` function):**
   - After multipart upload completion, downloads the final file
   - Computes SHA-256 hash of the complete file
   - Stores hash in DynamoDB package metadata as `sha256_hash` field

#### Download Process

**Location:** `src/services/s3_service.py` and `src/services/package_service.py`

1. **Direct Download (`download_model` function):**
   - Accepts optional `expected_hash` parameter
   - Downloads file from S3
   - Computes hash of downloaded content
   - Compares with expected hash (case-insensitive)
   - Returns HTTP 422 if hash mismatch detected

2. **Presigned URL Download (`get_download_url` function):**
   - Retrieves stored hash from DynamoDB
   - Optionally verifies hash before generating presigned URL (default: `verify_hash=true`)
   - Includes hash in response for client-side verification
   - Returns HTTP 422 if hash verification fails

### Database Schema

The `sha256_hash` field is stored in DynamoDB `packages` table:

```json
{
  "pkg_key": "package-name/1.0.0",
  "sha256_hash": "a1b2c3d4e5f6...",
  ...
}
```

### API Response

**Download URL Response:**

```json
{
  "url": "https://s3.amazonaws.com/...",
  "expires_at": "2025-11-14T10:00:00Z",
  "sha256_hash": "a1b2c3d4e5f6..." // Optional, if available
}
```

**Package List Response:**

```json
{
  "pkg_key": "package-name/1.0.0",
  "sha256_hash": "a1b2c3d4e5f6...",  // Optional, if available
  ...
}
```

### Usage Examples

**Upload with hash:**

```python
result = upload_model(file_content, "my-model", "1.0.0")
hash = result["sha256_hash"]  # Store this for verification
```

**Download with verification:**

```python
# Option 1: Pass hash directly
file_content = download_model("my-model", "1.0.0", expected_hash="a1b2c3...")

# Option 2: Get hash from API and verify client-side
response = get_download_url("my-model", "1.0.0", verify_hash=True)
hash = response.sha256_hash
# Download from URL and verify hash client-side
```

### Error Handling

- **Hash Mismatch:** Returns HTTP 422 with detailed error message
- **Missing Hash:** Verification is skipped if hash not provided/available
- **Backward Compatibility:** All hash verification is optional, existing code continues to work

### Security Benefits

- ✅ **Data Integrity:** Detects tampering or corruption
- ✅ **Audit Trail:** Hash stored in DynamoDB for compliance
- ✅ **Client Verification:** Clients can verify downloads independently
- ✅ **Non-Repudiation:** Hash proves file content at upload time

---

## S3 SSE-KMS Encryption

### Overview

S3 buckets are configured with Server-Side Encryption using AWS Key Management Service (SSE-KMS) with customer-managed keys. This provides enhanced security, auditability, and key management capabilities compared to default AES256 encryption.

### Implementation Details

#### Configuration

**Location:** `infra/modules/s3/main.tf`

```hcl
resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
  }
}
```

#### KMS Key

**Location:** `infra/modules/monitoring/main.tf`

- KMS key: `alias/acme-main-key`
- Description: "KMS key for ACME project encryption"
- Deletion window: 7 days
- Used for:
  - S3 object encryption
  - Secrets Manager encryption (JWT secrets)

#### IAM Policies

**Location:** `infra/envs/dev/iam_api.tf` and `infra/envs/dev/iam_validator.tf`

IAM policies enforce KMS encryption:

```json
{
  "Condition": {
    "StringEquals": {
      "s3:x-amz-server-side-encryption": "aws:kms"
    }
  }
}
```

This ensures all S3 operations must use KMS encryption.

### Benefits Over AES256 (SSE-S3)

| Feature        | AES256 (SSE-S3) | SSE-KMS                            |
| -------------- | --------------- | ---------------------------------- |
| Key Management | AWS-managed     | Customer-managed                   |
| Key Rotation   | Automatic       | Manual control                     |
| Audit Trail    | Limited         | CloudTrail logs                    |
| Access Control | Basic           | Fine-grained IAM                   |
| Compliance     | Basic           | Enhanced                           |
| Cost           | Free            | ~$0.03 per 10K requests + $1/month |

### Migration Notes

**Existing Objects:**

- Objects uploaded before SSE-KMS migration remain encrypted with AES256
- New objects automatically use SSE-KMS
- To re-encrypt existing objects, use S3 batch operations:
  ```bash
  aws s3 cp s3://pkg-artifacts/packages/old-file.zip \
    s3://pkg-artifacts/packages/old-file.zip \
    --sse aws:kms --sse-kms-key-id alias/acme-main-key
  ```

### Verification

Check S3 bucket encryption:

```bash
aws s3api get-bucket-encryption --bucket pkg-artifacts
```

Expected output:

```json
{
  "ServerSideEncryptionConfiguration": {
    "Rules": [
      {
        "ApplyServerSideEncryptionByDefault": {
          "SSEAlgorithm": "aws:kms",
          "KMSMasterKeyID": "arn:aws:kms:us-east-1:...:key/..."
        }
      }
    ]
  }
}
```

### Security Benefits

- ✅ **Customer-Managed Keys:** Full control over encryption keys
- ✅ **Audit Trail:** All key usage logged in CloudTrail
- ✅ **Key Rotation:** Manual rotation capability for compliance
- ✅ **Fine-Grained Access:** IAM policies control key usage
- ✅ **Compliance:** Meets regulatory requirements (HIPAA, PCI-DSS, etc.)

---

## Terraform Configuration

### Variables

**Location:** `infra/envs/dev/variables.tf`

All variables have sensible defaults to avoid prompts during `terraform plan`:

```hcl
variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for resource deployment"
}

variable "artifacts_bucket" {
  type        = string
  default     = "pkg-artifacts"
  description = "S3 bucket name for storing package artifacts"
}

variable "image_tag" {
  type        = string
  default     = "latest"
  description = "Docker image tag for the validator service"
}

variable "aws_account_id" {
  type        = string
  description = "AWS account ID"
  default     = "838693051036"
}
```

### Module Structure

**Location:** `infra/envs/dev/main.tf`

```hcl
module "s3" {
  source         = "../../modules/s3"
  artifacts_name = var.artifacts_bucket
  kms_key_arn    = module.monitoring.kms_key_arn
}

module "monitoring" {
  source                = "../../modules/monitoring"
  artifacts_bucket      = local.artifacts_bucket
  validator_service_url = "http://placeholder"
  ddb_tables_arnmap     = local.ddb_tables_arnmap
}
```

### Usage

**Run with defaults:**

```bash
cd infra/envs/dev
terraform init
terraform plan  # No prompts - uses all defaults
terraform apply
```

**Override variables:**

```bash
# Via command line
terraform plan -var="aws_region=us-west-2" -var="artifacts_bucket=my-bucket"

# Via terraform.tfvars file
cat > terraform.tfvars <<EOF
aws_region = "us-east-1"
artifacts_bucket = "pkg-artifacts-dev"
image_tag = "v1.2.3"
EOF
terraform plan -var-file="terraform.tfvars"
```

### Module Dependencies

```
main.tf
├── module.s3
│   └── requires: module.monitoring.kms_key_arn
├── module.monitoring
│   └── creates: KMS key (acme-main-key)
├── module.iam
├── module.ecs
└── module.api_gateway
    └── requires: module.monitoring.kms_key_arn
```

### Best Practices

1. **Always use defaults:** Variables have sensible defaults for development
2. **Override for production:** Use `terraform.tfvars` for environment-specific values
3. **Version control:** Never commit `terraform.tfvars` with secrets
4. **State management:** Terraform state is stored in S3 with encryption enabled
5. **Backend configuration:** Backend uses `pkg-artifacts` bucket (configured in `main.tf`)

---

## Related Documentation

- [STRIDE Coverage Analysis](./STRIDE_COVERAGE_ANALYSIS.md) - Security threat analysis
- [Security Operations Guide](./SECURITY.md) - Security operations and incident response
- [AWS Setup Guide](../AWS_SETUP_GUIDE.md) - AWS infrastructure setup
- [AWS Implementation Summary](../AWS_IMPLEMENTATION_SUMMARY.md) - Overall AWS architecture

---

## Changelog

### 2025-11-14

- ✅ **Implemented SHA-256 hash verification** for package uploads and downloads
- ✅ **Migrated S3 encryption from AES256 to SSE-KMS** with customer-managed KMS key
- ✅ **Updated Terraform variables** with defaults to eliminate prompts
- ✅ **Added comprehensive documentation** for all security implementations

---

## Support

For questions or issues related to security implementations:

1. Check [STRIDE Coverage Analysis](./STRIDE_COVERAGE_ANALYSIS.md) for security status
2. Review [Security Operations Guide](./SECURITY.md) for operational procedures
3. Consult AWS documentation for KMS and S3 encryption details
