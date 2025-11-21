# AWS Secrets Manager Guide

**Date:** 2025-11-21  
**Last Updated:** 2025-11-21

This guide explains how to find, retrieve, and manage secrets stored in AWS Secrets Manager for this project.

## Secrets Used in This Project

The project uses two types of secrets:

1. **JWT Secret** (`acme-jwt-secret`)
   - Used for signing and validating JWT tokens
   - Stored as JSON with fields: `jwt_secret`, `jwt_algorithm`, `jwt_expiration_hours`, `jwt_max_uses`
   - Location: Defined in `infra/modules/monitoring/main.tf`

2. **Admin Password Secret** (configurable via `AUTH_ADMIN_SECRET_NAME`)
   - Used for admin/grader authentication
   - Can be stored as:
     - List: `["password1", "password2"]`
     - Object: `{"passwords": ["password1", "password2"]}`
   - Environment variable: `AUTH_ADMIN_SECRET_NAME`

---

## Method 1: AWS Console (Web UI)

### Finding Secrets

1. **Log in to AWS Console**
   - Go to https://console.aws.amazon.com/
   - Select the correct region (default: `us-east-1`)

2. **Navigate to Secrets Manager**
   - Search for "Secrets Manager" in the AWS services search bar
   - Or go to: https://console.aws.amazon.com/secretsmanager/

3. **View All Secrets**
   - You'll see a list of all secrets in your account/region
   - Look for:
     - `acme-jwt-secret` (JWT secret)
     - Your admin password secret (name from `AUTH_ADMIN_SECRET_NAME`)

4. **View Secret Details**
   - Click on a secret name to view details
   - Click **"Retrieve secret value"** to see the actual secret value
   - Note: You need appropriate IAM permissions (`secretsmanager:GetSecretValue`)

### Updating Secrets

1. Select the secret
2. Click **"Edit"** or **"Update secret value"**
3. Modify the JSON value
4. Click **"Save"**
5. **Important**: Redeploy your application to pick up the new secret value

---

## Method 2: AWS CLI

### Prerequisites

```bash
# Install AWS CLI if not already installed
# macOS:
brew install awscli

# Linux:
sudo apt-get install awscli

# Configure credentials
aws configure
```

### List All Secrets

```bash
# List all secrets in the region
aws secretsmanager list-secrets --region us-east-1

# Filter by name pattern
aws secretsmanager list-secrets --region us-east-1 \
  --filters Key=name,Values=acme
```

### Get Secret Value

```bash
# Get JWT secret
aws secretsmanager get-secret-value \
  --secret-id acme-jwt-secret \
  --region us-east-1 \
  --query SecretString \
  --output text | jq .

# Get admin password secret (replace with your secret name)
aws secretsmanager get-secret-value \
  --secret-id YOUR_ADMIN_SECRET_NAME \
  --region us-east-1 \
  --query SecretString \
  --output text | jq .
```

### Update Secret Value

```bash
# Update JWT secret
aws secretsmanager put-secret-value \
  --secret-id acme-jwt-secret \
  --secret-string '{
    "jwt_secret": "your-new-secret-key",
    "jwt_algorithm": "HS256",
    "jwt_expiration_hours": 10,
    "jwt_max_uses": 1000
  }' \
  --region us-east-1

# Update admin password secret (list format)
aws secretsmanager put-secret-value \
  --secret-id YOUR_ADMIN_SECRET_NAME \
  --secret-string '["NewPassword123!"]' \
  --region us-east-1

# Update admin password secret (object format)
aws secretsmanager put-secret-value \
  --secret-id YOUR_ADMIN_SECRET_NAME \
  --secret-string '{"passwords": ["Password1", "Password2"]}' \
  --region us-east-1
```

### Create New Secret

```bash
# Create admin password secret
aws secretsmanager create-secret \
  --name acme-admin-passwords \
  --description "Admin passwords for ACME project" \
  --secret-string '["SecurePassword123!"]' \
  --region us-east-1 \
  --kms-key-id alias/acme-main-key
```

---

## Method 3: Terraform

### View Secret Configuration

The JWT secret is defined in `infra/modules/monitoring/main.tf`:

```hcl
resource "aws_secretsmanager_secret" "jwt_secret" {
  name = "acme-jwt-secret"
  kms_key_id = aws_kms_key.main_key.arn
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id = aws_secretsmanager_secret.jwt_secret.id
  secret_string = jsonencode({
    jwt_secret           = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm        = "HS256"
    jwt_expiration_hours = 10
    jwt_max_uses         = 1000
  })
}
```

### Get Secret ARN

```bash
# From Terraform state
cd infra/envs/dev
terraform output

# Or query AWS directly
aws secretsmanager describe-secret \
  --secret-id acme-jwt-secret \
  --region us-east-1 \
  --query ARN \
  --output text
```

---

## Method 4: From Application Code

### Check Environment Variables

The application looks for secrets using these environment variables:

```bash
# JWT Secret (for validator service)
JWT_SECRET=<value-from-secrets-manager>

# Admin Password Secret
AUTH_ADMIN_SECRET_NAME=acme-admin-passwords
AWS_REGION=us-east-1
```

### Verify Secret Access

Check CloudWatch logs for secret retrieval errors:

```bash
# View ECS task logs
aws logs tail /ecs/validator-service --follow --region us-east-1

# Or in AWS Console:
# CloudWatch > Log groups > /ecs/validator-service
```

---

## Troubleshooting

### Secret Not Found

**Error**: `ResourceNotFoundException: Secrets Manager can't find the specified secret`

**Solutions**:

1. Verify the secret name matches exactly (case-sensitive)
2. Check you're in the correct AWS region
3. Verify the secret exists:
   ```bash
   aws secretsmanager describe-secret --secret-id acme-jwt-secret --region us-east-1
   ```

### Permission Denied

**Error**: `AccessDeniedException: User is not authorized to perform: secretsmanager:GetSecretValue`

**Solutions**:

1. Verify IAM role has `secretsmanager:GetSecretValue` permission
2. Check IAM policies in:
   - `infra/envs/dev/iam_validator.tf` (for validator service)
   - `infra/envs/dev/iam_api.tf` (for API service, if using admin secrets)
3. Verify KMS decrypt permissions for the secret's encryption key

### Invalid Secret Format

**Error**: `ValueError: No password entries found in secret dict`

**Solutions**:

1. Verify secret format matches expected structure:
   - List: `["password1", "password2"]`
   - Object: `{"passwords": ["password1", "password2"]}`
2. Check secret value:
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id YOUR_SECRET_NAME \
     --region us-east-1 | jq .SecretString
   ```

### Secret Not Updating After Change

**Solutions**:

1. **Redeploy the application** - Secrets are cached at startup
2. Restart ECS tasks:
   ```bash
   aws ecs update-service \
     --cluster validator-cluster \
     --service validator-service \
     --force-new-deployment \
     --region us-east-1
   ```
3. Clear application cache (if applicable)

---

## Security Best Practices

1. **Never commit secrets to Git**
   - Secrets should only exist in AWS Secrets Manager
   - Use environment variables to reference secret names/ARNs

2. **Rotate secrets regularly**
   - Change JWT secrets periodically
   - Rotate admin passwords after suspected leaks

3. **Use least-privilege IAM policies**
   - Only grant `GetSecretValue` to services that need it
   - Restrict to specific secret ARNs, not wildcards

4. **Enable secret versioning**
   - AWS Secrets Manager automatically versions secrets
   - Keep previous versions for rollback capability

5. **Monitor secret access**
   - Enable CloudTrail to audit secret access
   - Set up CloudWatch alarms for unusual access patterns

---

## Quick Reference

### Common Commands

```bash
# List all secrets
aws secretsmanager list-secrets --region us-east-1

# Get secret value
aws secretsmanager get-secret-value --secret-id SECRET_NAME --region us-east-1

# Update secret
aws secretsmanager put-secret-value --secret-id SECRET_NAME --secret-string '{"key": "value"}' --region us-east-1

# Describe secret (metadata)
aws secretsmanager describe-secret --secret-id SECRET_NAME --region us-east-1

# Delete secret (careful!)
aws secretsmanager delete-secret --secret-id SECRET_NAME --region us-east-1 --recovery-window-in-days 7
```

### Secret Names in This Project

- **JWT Secret**: `acme-jwt-secret`
- **Admin Passwords**: Configurable via `AUTH_ADMIN_SECRET_NAME` env var

### Expected Regions

- Default: `us-east-1`
- Override with `AWS_REGION` environment variable

---

## Additional Resources

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [AWS CLI Secrets Manager Commands](https://docs.aws.amazon.com/cli/latest/reference/secretsmanager/)
- Project Security Guide: `docs/security/SECURITY.md`
- IAM Policies: `infra/envs/dev/iam_*.tf`
