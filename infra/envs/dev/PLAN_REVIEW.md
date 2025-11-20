# Terraform Plan Review

## 📊 Summary
- **19 resources** to be created
- **4 resources** to be updated
- **1 resource** to be destroyed

## ✅ Resources to be CREATED

### AWS Config Module (9 resources)
1. **aws_config_configuration_recorder** - Records configuration changes
2. **aws_config_configuration_recorder_status** - Enables the recorder
3. **aws_config_delivery_channel** - Delivers config snapshots to S3
4. **aws_iam_role_policy** - Custom policy for Config role
5. **aws_iam_role_policy_attachment** - Attaches AWS managed policy
6. **aws_s3_bucket_lifecycle_configuration** - Lifecycle rules for Config snapshots
7. **aws_s3_bucket_public_access_block** - Blocks public access
8. **aws_s3_bucket_server_side_encryption_configuration** - KMS encryption
9. **aws_s3_bucket_versioning** - Enables versioning

### Monitoring Module (CloudTrail & Logs) (5 resources)
1. **aws_cloudtrail.audit_trail** - Main CloudTrail trail for audit logging
   - Multi-region trail
   - Log file validation enabled
   - S3 bucket: `pkg-artifacts-cloudtrail-logs-838693051036`
   - KMS encryption enabled
   - Tracks S3 and DynamoDB data events

2. **aws_cloudwatch_log_group.cloudtrail_logs** - CloudWatch Logs integration
   - Name: `/aws/cloudtrail/acme-audit-trail`
   - Retention: 90 days
   - KMS encrypted

3. **aws_s3_bucket_lifecycle_configuration** - Lifecycle for CloudTrail logs
4. **aws_s3_bucket_public_access_block** - Blocks public access
5. **aws_s3_bucket_server_side_encryption_configuration** - KMS encryption
6. **aws_s3_bucket_versioning** - Versioning for CloudTrail logs
7. **aws_s3_bucket_policy** - Policy allowing CloudTrail to write

### S3 Module (2 resources)
1. **aws_s3_bucket_server_side_encryption_configuration** - KMS encryption for artifacts bucket
2. **aws_s3_bucket_versioning** - Versioning for artifacts bucket

### API Gateway (1 resource)
1. **aws_api_gateway_deployment** - New deployment (triggers stage update)

## 🔄 Resources to be UPDATED

1. **module.api_gateway.aws_api_gateway_stage.main_stage**
   - Deployment ID will be updated (new API deployment)

2. **module.config.aws_iam_role.config_role**
   - Assume role policy will be updated to match Terraform config
   - Tags will be added

3. **module.config.aws_s3_bucket.config_snapshots**
   - Tags will be added/updated

4. **module.s3.aws_s3_bucket.artifacts**
   - `force_destroy` changed from `false` to `true`
   - ⚠️ **Note**: This allows bucket deletion even if it contains objects

## ⚠️ Resources to be DESTROYED

1. **module.api_gateway.aws_api_gateway_deployment** (old deployment)
   - This is normal - old deployment replaced by new one
   - No impact on service availability

## 🔍 Key Changes Analysis

### ✅ Safe Changes
- All new resources are security/compliance related (Config, CloudTrail)
- S3 encryption and versioning are security best practices
- CloudTrail will provide audit logging
- AWS Config will track configuration changes

### ⚠️ Items to Review

1. **S3 force_destroy = true**
   - Allows bucket deletion even with objects
   - **Recommendation**: Consider if this is desired for production
   - If you want to prevent accidental deletion, change to `false`

2. **CloudTrail Event Selectors**
   - Will log ALL S3 and DynamoDB data events
   - This generates significant logs (cost consideration)
   - **Recommendation**: Monitor CloudTrail costs after deployment

3. **AWS Config Recorder**
   - Will record ALL resource types
   - Generates snapshots every 24 hours
   - **Recommendation**: Monitor Config costs

## 💰 Cost Implications

- **CloudTrail**: ~$2/month base + $0.10/GB for data events
- **AWS Config**: ~$2/month per configuration recorder + $0.003 per configuration item recorded
- **CloudWatch Logs**: ~$0.50/GB ingested, $0.03/GB stored
- **S3 Storage**: Minimal (lifecycle rules move to Glacier after 90 days)

## ✅ Pre-Apply Checklist

- [x] All existing resources imported
- [x] Circular dependencies resolved
- [x] KMS key reference fixed
- [ ] Review `force_destroy = true` for S3 bucket
- [ ] Verify KMS key permissions are correct
- [ ] Ensure sufficient IAM permissions for Terraform

## 🚀 Ready to Apply?

If everything looks good, run:
```bash
terraform apply tfplan
```

Or to review specific resources:
```bash
terraform show tfplan | grep -A 20 "module.monitoring.aws_cloudtrail"
```

