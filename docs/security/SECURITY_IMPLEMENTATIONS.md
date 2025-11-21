# Security Implementations Guide

**Date:** 2025-11-21  
**Last Updated:** 2025-11-21

This document details the security features implemented in the CS_450_Phase_2 project, including SHA-256 hash verification, S3 SSE-KMS encryption, CloudTrail audit logging, and Terraform configuration.

## Table of Contents

1. [SHA-256 Hash Verification](#sha-256-hash-verification)
2. [S3 SSE-KMS Encryption](#s3-sse-kms-encryption)
3. [JWT Secret Management with KMS](#jwt-secret-management-with-kms)
4. [CloudTrail Audit Logging](#cloudtrail-audit-logging)
5. [Terraform Configuration](#terraform-configuration)

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

## JWT Secret Management with KMS

### Overview

JWT secret is now stored in AWS Secrets Manager and encrypted with AWS KMS, replacing the previous plain environment variable approach. This ensures the secret is encrypted at rest and accessed securely via IAM policies.

### Implementation Details

#### Secret Storage

**Location:** `infra/modules/monitoring/main.tf`

1. **Secrets Manager Secret:**
   - Secret name: `acme-jwt-secret`
   - Encrypted with KMS key: `alias/acme-main-key`
   - Stored as JSON with fields: `jwt_secret`, `jwt_algorithm`, `jwt_expiration_hours`, `jwt_max_uses`

2. **KMS Key:**
   - Key alias: `alias/acme-main-key`
   - Used for encrypting the Secrets Manager secret
   - IAM policies grant decrypt permissions to ECS execution role

#### Application Code

**Location:** `src/utils/jwt_secret.py`

1. **Secret Retrieval Function:**
   - `get_jwt_secret()` retrieves secret from Secrets Manager
   - Implements caching to avoid repeated Secrets Manager calls
   - Falls back to `JWT_SECRET` environment variable for local development
   - Falls back to generating a temporary secret if neither is available (local dev only)

2. **Usage in Application:**
   - `src/middleware/jwt_auth.py`: Uses `get_jwt_secret()` to retrieve secret
   - `src/services/auth_service.py`: Uses `get_jwt_secret()` for token signing/verification
   - `src/entrypoint.py`: Uses `get_jwt_secret()` to check if auth should be enabled

#### ECS Task Definition

**Location:** `infra/modules/ecs/main.tf`

1. **Secret Injection:**
   - ECS task definition injects JWT secret from Secrets Manager
   - Secret injected as `JWT_SECRET` environment variable
   - `JWT_SECRET_NAME` environment variable set to `acme-jwt-secret`

2. **IAM Permissions:**
   - ECS execution role has `secretsmanager:GetSecretValue` permission
   - ECS execution role has `kms:Decrypt` permission for Secrets Manager service
   - IAM policies in `infra/envs/dev/iam_validator.tf` grant Secrets Manager access

### Security Benefits

1. **Encryption at Rest:**
   - Secret encrypted with KMS before storage in Secrets Manager
   - Cannot be read without KMS decrypt permissions

2. **Access Control:**
   - Only services with IAM permissions can retrieve the secret
   - No plain-text secret in environment variables or code

3. **Audit Trail:**
   - Secrets Manager logs all secret access attempts
   - CloudTrail tracks KMS decrypt operations

4. **Secret Rotation:**
   - Secrets Manager supports automatic secret rotation
   - Can update secret without code changes

### Local Development

For local development, the code falls back to:

1. `JWT_SECRET` environment variable (if set)
2. Generated temporary secret (if neither Secrets Manager nor env var available)

This allows local development without AWS credentials while maintaining security in production.

### Configuration

**Environment Variables:**

- `JWT_SECRET_NAME`: Name of the Secrets Manager secret (default: `acme-jwt-secret`)
- `JWT_SECRET`: Fallback environment variable for local development
- `AWS_REGION`: AWS region for Secrets Manager (default: `us-east-1`)

**Terraform Variables:**

- Secret name: `acme-jwt-secret` (defined in `infra/modules/monitoring/main.tf`)
- KMS key: `alias/acme-main-key` (defined in `infra/modules/monitoring/main.tf`)

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
  - Secrets Manager encryption (JWT secrets) - JWT secret stored in Secrets Manager with KMS encryption, retrieved via `src/utils/jwt_secret.py`

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

## CloudTrail Audit Logging

### Overview

AWS CloudTrail is explicitly configured to provide comprehensive audit logging for all API calls and data events. This ensures compliance, security monitoring, and non-repudiation capabilities.

### Implementation Details

**Location:** `infra/modules/monitoring/main.tf`

#### CloudTrail Trail Configuration

```hcl
resource "aws_cloudtrail" "audit_trail" {
  name                          = "acme-audit-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_logging                = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.main_key.arn
  # ... event selectors for S3 and DynamoDB ...
}
```

#### Key Features

- **Multi-region trail:** Captures events from all AWS regions
- **Global service events:** Includes IAM, CloudFront, Route 53 events
- **Data event logging:** Logs S3 and DynamoDB data operations
- **KMS encryption:** All log files encrypted with project KMS key
- **Log file validation:** SHA-256 hash validation detects tampering

#### Event Selectors

**S3 Data Events:**

- Logs all operations on the artifacts bucket (`GetObject`, `PutObject`, `DeleteObject`, `ListBucket`)

**DynamoDB Data Events:**

- Logs all operations on DynamoDB tables (`PutItem`, `GetItem`, `DeleteItem`, `Query`, `Scan`)

#### Log Storage

**S3 Bucket:** `{artifacts_bucket}-cloudtrail-logs-{account-id}`

- Encryption: SSE-KMS with `acme-main-key`
- Versioning: Enabled (prevents log deletion)
- Public access: Blocked
- Lifecycle: Transitions to Glacier after 90 days

**CloudWatch Logs:** `/aws/cloudtrail/acme-audit-trail`

- Retention: 90 days
- Encryption: KMS

### Security Benefits

- ✅ **Non-Repudiation:** Immutable audit logs prove who did what, when, and where
- ✅ **Log Integrity:** Log file validation and S3 versioning prevent tampering
- ✅ **Compliance:** Supports SOC 2, HIPAA, PCI DSS, GDPR requirements
- ✅ **Security Monitoring:** Enables detection of unauthorized access, privilege escalation, data exfiltration
- ✅ **Forensics:** Complete audit trail for incident investigation

### Verification

Check trail status:

```bash
aws cloudtrail get-trail-status --name acme-audit-trail
```

Verify log files in S3:

```bash
aws s3 ls s3://{bucket-name}/AWSLogs/{account-id}/CloudTrail/ --recursive
```

Look up recent events:

```bash
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutObject \
  --max-results 10
```

### Documentation

For detailed CloudTrail configuration, troubleshooting, and best practices, see:

- [CloudTrail Configuration Guide](./CLOUDTRAIL_CONFIGURATION.md)

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

### 2025-11-20

- ✅ **CloudTrail Audit Logging** – Explicitly configured CloudTrail trail with multi-region support, S3 and DynamoDB data event logging, KMS encryption, and log file validation. Includes dedicated S3 bucket with lifecycle management (Glacier transition after 90 days). See [CloudTrail Configuration Guide](./CLOUDTRAIL_CONFIGURATION.md) for details.

### 2025-11-18

- ✅ **Fixed OpenAPI specification compliance** – Updated `/authenticate` endpoint to return token string (not JSON object) and added 501 response when authentication unavailable. Updated `/tracks` endpoint to return `{"plannedTracks": [...]}`. Achieved 100% OpenAPI compliance (15/15 endpoints). See [OPENAPI_COMPLIANCE_CHECK.md](../../OPENAPI_COMPLIANCE_CHECK.md) for details.
- ✅ **Updated dependencies** – Fixed security vulnerabilities in Python (`jinja2`, `requests`) and Go (`github.com/ulikunitz/xz`, `golang.org/x/net`) dependencies addressing multiple CVEs.

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
