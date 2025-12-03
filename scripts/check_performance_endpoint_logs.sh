#!/bin/bash
# Script to check logs for performance endpoint issues

REGION="us-east-1"
ECS_LOG_GROUP="/ecs/validator-service"

echo "=========================================="
echo "Performance Endpoint Log Diagnostics"
echo "=========================================="
echo ""

# 1. Check ECS logs for [PERF] messages
echo "1. Checking ECS logs for [PERF] messages..."
echo "-------------------------------------------"
aws logs filter-log-events \
  --log-group-name "$ECS_LOG_GROUP" \
  --filter-pattern "[PERF]" \
  --region "$REGION" \
  --max-items 50 \
  --query 'events[*].[timestamp,message]' \
  --output table || echo "No [PERF] messages found or log group doesn't exist"
echo ""

# 2. Check for errors in ECS logs
echo "2. Checking ECS logs for errors..."
echo "-------------------------------------------"
aws logs filter-log-events \
  --log-group-name "$ECS_LOG_GROUP" \
  --filter-pattern "ERROR" \
  --region "$REGION" \
  --max-items 20 \
  --query 'events[*].[timestamp,message]' \
  --output table || echo "No errors found"
echo ""

# 3. Check for endpoint registration
echo "3. Checking for endpoint registration messages..."
echo "-------------------------------------------"
aws logs filter-log-events \
  --log-group-name "$ECS_LOG_GROUP" \
  --filter-pattern "Performance download endpoint" \
  --region "$REGION" \
  --max-items 10 \
  --query 'events[*].[timestamp,message]' \
  --output table || echo "No registration messages found"
echo ""

# 4. Get latest log stream
echo "4. Latest log stream info..."
echo "-------------------------------------------"
LATEST_STREAM=$(aws logs describe-log-streams \
  --log-group-name "$ECS_LOG_GROUP" \
  --order-by LastEventTime \
  --descending \
  --max-items 1 \
  --region "$REGION" \
  --query 'logStreams[0].logStreamName' \
  --output text)

if [ "$LATEST_STREAM" != "None" ] && [ -n "$LATEST_STREAM" ]; then
  echo "Latest stream: $LATEST_STREAM"
  echo ""
  echo "Last 20 log entries:"
  aws logs get-log-events \
    --log-group-name "$ECS_LOG_GROUP" \
    --log-stream-name "$LATEST_STREAM" \
    --limit 20 \
    --region "$REGION" \
    --query 'events[*].message' \
    --output text | tail -20
else
  echo "No log streams found"
fi
echo ""

# 5. Get API Gateway ID
echo "5. Getting API Gateway information..."
echo "-------------------------------------------"
API_ID=$(aws apigateway get-rest-apis \
  --region "$REGION" \
  --query "items[?name=='main-api'].id" \
  --output text)

if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
  echo "API Gateway ID: $API_ID"
  API_LOG_GROUP="/aws/apigateway/$API_ID/prod"
  echo "API Gateway Log Group: $API_LOG_GROUP"
  echo ""
  
  # Check if log group exists
  if aws logs describe-log-groups \
    --log-group-name-prefix "$API_LOG_GROUP" \
    --region "$REGION" \
    --query 'logGroups[0].logGroupName' \
    --output text | grep -q "$API_LOG_GROUP"; then
    
    echo "Searching for performance endpoint requests..."
    aws logs filter-log-events \
      --log-group-name "$API_LOG_GROUP" \
      --filter-pattern "performance" \
      --region "$REGION" \
      --max-items 20 \
      --query 'events[*].[timestamp,message]' \
      --output table || echo "No performance endpoint requests found"
  else
    echo "API Gateway log group not found (logging may not be enabled)"
  fi
else
  echo "Could not find API Gateway"
fi
echo ""

echo "=========================================="
echo "Diagnostics Complete"
echo "=========================================="

