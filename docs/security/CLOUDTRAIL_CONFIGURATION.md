# CloudTrail Configuration Guide

**Date:** 2025-11-21  
**Last Updated:** 2025-11-21

## Overview

AWS CloudTrail is explicitly configured in this project to provide comprehensive audit logging for all API calls and data events. This ensures compliance, security monitoring, and non-repudiation capabilities.

## Table of Contents

1. [Configuration Summary](#configuration-summary)
2. [Architecture](#architecture)
3. [Implementation Details](#implementation-details)
4. [Security Features](#security-features)
5. [Log Storage and Retention](#log-storage-and-retention)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

---

## Configuration Summary

**Location:** `infra/modules/monitoring/main.tf`

The CloudTrail configuration includes:

- ✅ **Multi-region trail** for global coverage
- ✅ **Global service events** (IAM, CloudFront, Route 53)
- ✅ **Data event logging** for S3 and DynamoDB
- ✅ **KMS encryption** for log files
- ✅ **Log file validation** enabled
- ✅ **Dedicated S3 bucket** for log storage
- ✅ **Lifecycle management** (transition to Glacier after 90 days)
- ✅ **Versioning enabled** on log bucket

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CloudTrail Trail                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Name: acme-audit-trail                               │  │
│  │  Multi-region: Yes                                    │  │
│  │  Global events: Yes                                   │  │
│  │  Log validation: Enabled                              │  │
│  │  Encryption: KMS (acme-main-key)                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Event Selectors                                      │  │
│  │  • S3 data events (artifacts bucket)                 │  │
│  │  • DynamoDB data events (all tables)                 │  │
│  │  • Management events (all)                            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              S3 Bucket: CloudTrail Logs                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Bucket: {artifacts_bucket}-cloudtrail-logs-{id}     │  │
│  │  Encryption: SSE-KMS                                  │  │
│  │  Versioning: Enabled                                  │  │
│  │  Public access: Blocked                               │  │
│  │  Lifecycle: Glacier after 90 days                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            CloudWatch Log Group (Optional)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Name: /aws/cloudtrail/acme-audit-trail              │  │
│  │  Retention: 90 days                                   │  │
│  │  Encryption: KMS                                      │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Implementation Details

### 1. CloudTrail Trail

**Resource:** `aws_cloudtrail.audit_trail`

```hcl
resource "aws_cloudtrail" "audit_trail" {
  name                          = "acme-audit-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_logging                = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.main_key.arn
  # ... event selectors ...
}
```

**Key Features:**

- **Multi-region:** Captures events from all AWS regions
- **Global service events:** Includes IAM, CloudFront, Route 53 events
- **Log file validation:** Detects tampering with log files
- **KMS encryption:** All log files encrypted with project KMS key

### 2. Event Selectors

#### S3 Data Events

Logs all data operations on the artifacts bucket:

```hcl
event_selector {
  read_write_type                 = "All"
  include_management_events       = true

  data_resource {
    type   = "AWS::S3::Object"
    values = ["arn:aws:s3:::${var.artifacts_bucket}/*"]
  }
}
```

**Captured Events:**

- `GetObject` - Package downloads
- `PutObject` - Package uploads
- `DeleteObject` - Package deletions
- `ListBucket` - Bucket listings

#### DynamoDB Data Events

Logs all data operations on DynamoDB tables:

```hcl
event_selector {
  read_write_type                 = "All"
  include_management_events       = true

  data_resource {
    type   = "AWS::DynamoDB::Table"
    values = values(var.ddb_tables_arnmap)
  }
}
```

**Captured Events:**

- `PutItem` - Record creation/updates
- `GetItem` - Record reads
- `DeleteItem` - Record deletions
- `Query` - Table queries
- `Scan` - Table scans

### 3. S3 Log Bucket

**Resource:** `aws_s3_bucket.cloudtrail_logs`

**Security Configuration:**

- **Encryption:** SSE-KMS with `acme-main-key`
- **Versioning:** Enabled (prevents log deletion)
- **Public access:** Blocked
- **Lifecycle:** Transitions to Glacier after 90 days
- **Bucket policy:** Allows CloudTrail service to write logs

**Bucket Policy:**
The bucket policy ensures:

- CloudTrail service can write logs
- Only CloudTrail from the specified trail can write
- Source account validation prevents cross-account writes

### 4. KMS Key Policy

The KMS key policy includes permissions for CloudTrail:

```json
{
  "Sid": "Allow CloudTrail to encrypt logs",
  "Effect": "Allow",
  "Principal": {
    "Service": "cloudtrail.amazonaws.com"
  },
  "Action": ["kms:GenerateDataKey", "kms:Decrypt"],
  "Condition": {
    "StringEquals": {
      "AWS:SourceArn": "arn:aws:cloudtrail:region:account:trail/acme-audit-trail"
    }
  }
}
```

---

## Security Features

### 1. Non-Repudiation

CloudTrail provides immutable audit logs that prove:

- **Who** performed an action (IAM user/role ARN)
- **What** action was performed (API call name)
- **When** it occurred (timestamp)
- **Where** it occurred (source IP, region)
- **Result** (success/failure)

### 2. Log Integrity

- **Log file validation:** SHA-256 hash validation detects tampering
- **S3 versioning:** Prevents accidental or malicious log deletion
- **KMS encryption:** Protects logs at rest
- **Immutable storage:** Logs cannot be modified after creation

### 3. Compliance

CloudTrail logs support compliance requirements for:

- **SOC 2:** Audit trail for access controls
- **HIPAA:** Audit logging for PHI access
- **PCI DSS:** Transaction logging
- **GDPR:** Data access logging

### 4. Security Monitoring

CloudTrail enables detection of:

- Unauthorized access attempts
- Privilege escalation
- Data exfiltration
- Configuration changes
- Policy violations

---

## Log Storage and Retention

### Storage Locations

1. **S3 Bucket:** Primary storage for CloudTrail log files
   - Path: `s3://{bucket-name}/AWSLogs/{account-id}/CloudTrail/`
   - Format: JSON log files (gzipped)

2. **CloudWatch Logs:** Optional integration for real-time analysis
   - Log group: `/aws/cloudtrail/acme-audit-trail`
   - Retention: 90 days

### Lifecycle Management

- **Days 0-90:** Standard S3 storage
- **Days 90+:** Transitioned to Glacier for cost optimization
- **Retention:** Indefinite (compliance requirement)

### Log File Structure

CloudTrail log files contain:

```json
{
  "Records": [
    {
      "eventVersion": "1.08",
      "userIdentity": {
        "type": "IAMUser",
        "principalId": "...",
        "arn": "arn:aws:iam::account:user/username",
        "accountId": "...",
        "userName": "username"
      },
      "eventTime": "2025-01-XX...",
      "eventSource": "s3.amazonaws.com",
      "eventName": "GetObject",
      "awsRegion": "us-east-1",
      "sourceIPAddress": "...",
      "resources": [
        {
          "type": "AWS::S3::Object",
          "ARN": "arn:aws:s3:::bucket/key"
        }
      ],
      "responseElements": {...},
      "requestParameters": {...}
    }
  ]
}
```

---

## Verification

### 1. Check Trail Status

```bash
aws cloudtrail get-trail-status --name acme-audit-trail
```

**Expected Output:**

```json
{
  "IsLogging": true,
  "LatestCloudWatchLogsDeliveryTime": "...",
  "LatestDeliveryTime": "...",
  "StartLoggingTime": "...",
  "LatestDigestDeliveryTime": "..."
}
```

### 2. Verify Log Files in S3

```bash
aws s3 ls s3://{bucket-name}/AWSLogs/{account-id}/CloudTrail/ --recursive
```

### 3. Test Event Capture

Perform an action (e.g., upload a package) and verify it appears in CloudTrail:

```bash
# Wait 5-15 minutes for log delivery
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=PutObject \
  --max-results 10
```

### 4. Verify Encryption

```bash
aws s3api get-object-attributes \
  --bucket {bucket-name} \
  --key {log-file-path} \
  --object-attributes ServerSideEncryption
```

**Expected:** `SSE-KMS` with KMS key ID

### 5. Check Log File Validation

```bash
aws cloudtrail validate-logs \
  --trail-name acme-audit-trail \
  --start-time 2025-01-01T00:00:00Z \
  --end-time 2025-01-02T00:00:00Z
```

---

## Troubleshooting

### Issue: Trail Not Logging

**Symptoms:**

- `IsLogging: false` in trail status
- No log files in S3 bucket

**Solutions:**

1. Check S3 bucket policy allows CloudTrail service
2. Verify KMS key policy allows CloudTrail
3. Check IAM permissions for CloudTrail service role
4. Review CloudTrail service quotas

### Issue: Missing Data Events

**Symptoms:**

- Management events logged but data events missing

**Solutions:**

1. Verify event selectors are configured correctly
2. Check data event selectors include correct resource ARNs
3. Ensure `read_write_type = "All"` is set
4. Wait 5-15 minutes for log delivery

### Issue: Log Files Not Encrypted

**Symptoms:**

- Log files in S3 without encryption

**Solutions:**

1. Verify `kms_key_id` is set in trail configuration
2. Check KMS key policy allows CloudTrail
3. Verify S3 bucket encryption is configured
4. Check KMS key is in the same region as trail

### Issue: High S3 Costs

**Symptoms:**

- Unexpected S3 charges from CloudTrail logs

**Solutions:**

1. Enable lifecycle policy to transition to Glacier
2. Review event selectors (data events generate more logs)
3. Consider filtering unnecessary events
4. Archive old logs to Glacier

---

## Best Practices

1. **Regular Review:** Review CloudTrail logs weekly for anomalies
2. **Alerting:** Set up CloudWatch alarms for suspicious activities
3. **Access Control:** Limit who can view CloudTrail logs
4. **Backup:** Consider cross-region replication for disaster recovery
5. **Monitoring:** Use CloudWatch Insights for log analysis
6. **Compliance:** Retain logs per compliance requirements (typically 7 years)

---

## Related Documentation

- [Security Audit Report](./SECURITY_AUDIT_REPORT.md) - Risk R-009 resolution
- [STRIDE Threat Model](./stride-threat-level.md) - Repudiation mitigation
- [Security Implementations](./SECURITY_IMPLEMENTATIONS.md) - Overall security features
- [AWS CloudTrail User Guide](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/)

---

## Terraform Outputs

After deployment, the following outputs are available:

```hcl
output "cloudtrail_trail_arn" {
  value = module.monitoring.cloudtrail_trail_arn
}

output "cloudtrail_logs_bucket" {
  value = module.monitoring.cloudtrail_logs_bucket
}
```

**Access via:**

```bash
terraform output cloudtrail_trail_arn
terraform output cloudtrail_logs_bucket
```

---

## Change Log

- **2025-11-20:** Initial CloudTrail configuration added
  - Multi-region trail
  - S3 and DynamoDB data event logging
  - KMS encryption
  - Log file validation
  - Dedicated S3 bucket with lifecycle management
