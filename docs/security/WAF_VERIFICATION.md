# AWS WAF Configuration Verification Guide

## Overview

This document provides steps to verify that AWS WAF is properly configured and protecting the CloudFront distribution against DoS attacks and common web vulnerabilities.

## Configuration Summary

### WAF Module Location

- **Module:** `infra/modules/waf/main.tf`
- **Integration:** `infra/envs/dev/main.tf` (lines 68-77)
- **CloudFront Association:** `infra/modules/cloudfront/main.tf` (line 254)

### Security Rules Configured

1. **AWS Managed Rules - Core Rule Set (OWASP Top 10)**
   - Priority: 1
   - Protects against common web vulnerabilities

2. **AWS Managed Rules - Known Bad Inputs**
   - Priority: 2
   - Blocks known malicious input patterns

3. **AWS Managed Rules - Linux Operating System**
   - Priority: 3
   - Protects against Linux-specific attacks

4. **AWS Managed Rules - SQL Injection**
   - Priority: 4
   - Blocks SQL injection attempts

5. **Rate-based Rule (DoS Protection)**
   - Priority: 5
   - Rate limit: 2000 requests per 5 minutes per IP
   - Action: Block

6. **Size Restrictions**
   - Priority: 6
   - Blocks requests with:
     - Body > 10 MB
     - URI path > 8 KB
     - Query string > 8 KB

## Verification Steps

### 1. Terraform Validation

```bash
cd infra/envs/dev
terraform init
terraform validate
terraform plan
```

**Expected Output:**

- No errors in validation
- WAF module should be created
- CloudFront distribution should show `web_acl_id` association

### 2. Verify WAF Web ACL Creation

After deployment, verify the WAF Web ACL exists:

```bash
aws wafv2 get-web-acl \
  --scope CLOUDFRONT \
  --name acme-waf-dev \
  --region us-east-1
```

**Expected Output:**

- Web ACL should exist with name `acme-waf-dev`
- Should show 6 rules configured
- Default action should be "Allow"

### 3. Verify CloudFront Association

```bash
aws cloudfront get-distribution \
  --id <distribution-id> \
  --query 'Distribution.DistributionConfig.WebACLId'
```

**Expected Output:**

- Should return the WAF Web ACL ARN
- Format: `arn:aws:wafv2:us-east-1:...:global/webacl/acme-waf-dev/...`

### 4. Test Rate Limiting (DoS Protection)

Send multiple rapid requests to test rate limiting:

```bash
# Send 2100 requests rapidly (exceeds 2000 limit)
for i in {1..2100}; do
  curl -s -o /dev/null -w "%{http_code}\n" https://<cloudfront-domain>/
done
```

**Expected Behavior:**

- First 2000 requests should succeed (200 status)
- Requests 2001+ should be blocked (403 Forbidden)
- Blocked requests should appear in WAF logs

### 5. Test SQL Injection Protection

```bash
curl "https://<cloudfront-domain>/api/packages?name=' OR '1'='1"
```

**Expected Behavior:**

- Request should be blocked (403 Forbidden)
- Should trigger SQL Injection rule

### 6. Test Size Restrictions

```bash
# Test oversized URI path
curl "https://<cloudfront-domain>/$(python3 -c "print('A' * 9000)")"

# Test oversized query string
curl "https://<cloudfront-domain>/api/packages?param=$(python3 -c "print('A' * 9000)")"
```

**Expected Behavior:**

- Requests should be blocked (403 Forbidden)
- Should trigger Size Restrictions rule

### 7. Verify WAF Logging

Check S3 bucket for WAF logs:

```bash
aws s3 ls s3://acme-waf-logs-dev-<account-id>/waf-logs/
```

**Expected Output:**

- Log files should appear within 5-15 minutes of traffic
- Log format: `AWSLogs/<account-id>/WAFLogs/us-east-1/<web-acl-name>/YYYY/MM/DD/...`

### 8. Monitor CloudWatch Metrics

Check CloudWatch metrics for WAF:

```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/WAFV2 \
  --metric-name AllowedRequests \
  --dimensions Name=WebACL,Value=acme-waf-dev Name=Region,Value=CloudFront \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

**Expected Output:**

- Metrics should show allowed/blocked request counts
- Should see metrics for each rule

## Troubleshooting

### Issue: WAF not blocking requests

**Possible Causes:**

1. WAF not associated with CloudFront distribution
2. Rules have incorrect priority
3. Default action is "Allow" and rules are set to "Count"

**Solution:**

- Verify CloudFront distribution has `web_acl_id` set
- Check rule priorities and actions
- Ensure rate-based rule has action "Block"

### Issue: WAF logs not appearing in S3

**Possible Causes:**

1. S3 bucket policy not configured correctly
2. WAF logging not enabled
3. No traffic hitting the distribution

**Solution:**

- Verify S3 bucket policy allows `delivery.logs.amazonaws.com`
- Check WAF logging configuration
- Generate test traffic

### Issue: Terraform plan shows errors

**Possible Causes:**

1. Provider not configured for us-east-1
2. Missing variables
3. Syntax errors in WAF module

**Solution:**

- Ensure `aws.us_east_1` provider is configured
- Check all required variables are provided
- Validate Terraform syntax

## Configuration Files

### Key Files Modified/Created

1. **`infra/modules/waf/main.tf`** - WAF Web ACL configuration
2. **`infra/modules/waf/variables.tf`** - WAF module variables
3. **`infra/modules/cloudfront/main.tf`** - CloudFront WAF association
4. **`infra/envs/dev/main.tf`** - WAF module integration

### Deployment

```bash
cd infra/envs/dev
terraform init
terraform plan  # Review changes
terraform apply # Deploy WAF
```

## Security Notes

- WAF is deployed in `us-east-1` region (required for CloudFront)
- Rate limit is configurable via `rate_limit` variable (default: 2000)
- WAF logs are stored in S3 with encryption and lifecycle policies
- All rules have CloudWatch metrics enabled for monitoring

## References

- [AWS WAF Documentation](https://docs.aws.amazon.com/waf/)
- [CloudFront WAF Integration](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/distribution-web-acl.html)
- [WAF Logging Configuration](https://docs.aws.amazon.com/waf/latest/developerguide/logging.html)
