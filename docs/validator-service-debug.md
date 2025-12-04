# Validator Service Exit Code 1 Debugging Guide

## 🚨 Critical Information Needed

### 1. Get Task Definition (containerDefinitions)

Run this command to get the exact container configuration:

```bash
aws ecs describe-task-definition \
  --task-definition validator-service \
  --query 'taskDefinition.containerDefinitions[0]' \
  --output json > task-definition-container.json
```

Or for just the containerDefinitions section:

```bash
aws ecs describe-task-definition \
  --task-definition validator-service \
  --query 'taskDefinition.containerDefinitions' \
  --output json
```

### 2. Dockerfile Location

The Dockerfile is at: `Dev-ACME/Dockerfile.validator`

**Key fixes applied:**
- ✅ Added `ENV PYTHONUNBUFFERED=1` for immediate log flushing
- ✅ Changed CMD to use `python -u` for unbuffered output

### 3. Get CloudWatch Logs

Check if logs exist:

```bash
# List log groups
aws logs describe-log-groups \
  --log-group-name-prefix "/ecs/validator-service" \
  --region us-east-1

# List recent log streams
aws logs describe-log-streams \
  --log-group-name "/ecs/validator-service" \
  --order-by LastEventTime \
  --descending \
  --max-items 5 \
  --region us-east-1

# Get latest log events (replace STREAM_NAME with actual stream name)
aws logs get-log-events \
  --log-group-name "/ecs/validator-service" \
  --log-stream-name "STREAM_NAME" \
  --limit 100 \
  --region us-east-1 \
  --output text
```

**Or tail logs in real-time:**

```bash
aws logs tail /ecs/validator-service --follow --region us-east-1
```

### 4. Get ECS Task Status

Check current task status:

```bash
# Get running tasks
aws ecs list-tasks \
  --cluster validator-cluster \
  --service-name validator-service \
  --region us-east-1

# Describe a specific task (replace TASK_ARN)
aws ecs describe-tasks \
  --cluster validator-cluster \
  --tasks TASK_ARN \
  --region us-east-1 \
  --query 'tasks[0].{lastStatus:lastStatus,stoppedReason:stoppedReason,exitCode:containers[0].exitCode}'
```

## 🔍 Most Common Issues

### Issue 1: Missing/Invalid RDS Connection

The validator service has RDS environment variables but **doesn't use RDS directly**. However, check:

```bash
# Verify RDS endpoint is accessible from ECS task
# Check security group allows outbound to RDS port 5432
# Verify RDS endpoint format (should be just hostname, no port)
```

**RDS Environment Variables in Task Definition:**
- `RDS_ENDPOINT` - Should be hostname only (no :5432)
- `RDS_DATABASE` - Database name
- `RDS_USERNAME` - Username
- `RDS_PASSWORD` - Password

### Issue 2: Missing Secrets (JWT_SECRET or GITHUB_TOKEN)

If Secrets Manager access fails, container will crash. Check:

```bash
# Verify secrets exist
aws secretsmanager describe-secret \
  --secret-id <JWT_SECRET_ARN> \
  --region us-east-1

# Verify ECS execution role has permissions
aws iam get-role-policy \
  --role-name ecs-execution-role \
  --policy-name ecs-execution-secrets-policy
```

### Issue 3: Missing DynamoDB Tables

Validator service uses DynamoDB. Verify tables exist:

```bash
aws dynamodb list-tables --region us-east-1 | grep -E "(packages|downloads)"
```

Required tables:
- `packages`
- `downloads`

### Issue 4: Python Module Import Error

The validator service requires these modules (check requirements.txt):
- fastapi
- uvicorn
- boto3
- pydantic

**To test locally:**
```bash
docker build -f Dockerfile.validator -t validator-test .
docker run --rm validator-test python -c "import fastapi, uvicorn, boto3; print('All imports OK')"
```

### Issue 5: Port Already in Use or Binding Issue

The service binds to `0.0.0.0:3000`. If port is in use or binding fails, you'll see an immediate crash.

## 🔧 Quick Fixes Applied

1. **PYTHONUNBUFFERED=1** - Added to Dockerfile to ensure logs flush immediately
2. **python -u flag** - Added to CMD for unbuffered output
3. **Log configuration** - Already present in task definition (good!)

## 📋 Next Steps

1. **Rebuild and push the Docker image:**
   ```bash
   cd Dev-ACME
   docker build -f Dockerfile.validator -t validator-service:latest .
   docker tag validator-service:latest 838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service:latest
   docker push 838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service:latest
   ```

2. **Force new ECS deployment:**
   ```bash
   aws ecs update-service \
     --cluster validator-cluster \
     --service validator-service \
     --force-new-deployment \
     --region us-east-1
   ```

3. **Watch logs immediately:**
   ```bash
   aws logs tail /ecs/validator-service --follow --region us-east-1
   ```

## 🎯 Expected Log Output

When working correctly, you should see:

```
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:3000 (Press CTRL+C to quit)
Starting validator service on port 3000
```

If you see errors before this, note the exact error message.

