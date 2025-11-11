# Script to rebuild and redeploy the ECS service with debug logging

Write-Host "=== Rebuilding and Redeploying ECS Service ===" -ForegroundColor Cyan
Write-Host ""

$ECR_REPO = "838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service"
$REGION = "us-east-1"
$CLUSTER = "validator-cluster"
$SERVICE = "validator-service"

# Step 1: Login to ECR
Write-Host "1. Logging into ECR..." -ForegroundColor Yellow
$loginCommand = aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ ECR login successful" -ForegroundColor Green
} else {
    Write-Host "  ❌ ECR login failed: $loginCommand" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 2: Build Docker image
Write-Host "2. Building Docker image..." -ForegroundColor Yellow
docker build -t validator-service:latest .
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Docker image built successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 3: Tag image for ECR
Write-Host "3. Tagging image for ECR..." -ForegroundColor Yellow
docker tag validator-service:latest "${ECR_REPO}:latest"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Image tagged successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ Image tagging failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 4: Push to ECR
Write-Host "4. Pushing image to ECR..." -ForegroundColor Yellow
docker push "${ECR_REPO}:latest"
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Image pushed successfully" -ForegroundColor Green
} else {
    Write-Host "  ❌ Image push failed" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 5: Force ECS service update
Write-Host "5. Forcing ECS service update..." -ForegroundColor Yellow
$updateResult = aws ecs update-service --cluster $CLUSTER --service $SERVICE --force-new-deployment --region $REGION 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ ECS service update initiated" -ForegroundColor Green
    Write-Host "  Service will restart with new image..." -ForegroundColor Cyan
} else {
    Write-Host "  ❌ ECS service update failed: $updateResult" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Step 6: Wait and check service status
Write-Host "6. Waiting for service to stabilize (this may take 2-3 minutes)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

$maxAttempts = 30
$attempt = 0
$stable = $false

while ($attempt -lt $maxAttempts -and -not $stable) {
    $serviceStatus = aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $REGION --query "services[0].[status,runningCount,desiredCount]" --output text 2>$null
    
    if ($serviceStatus) {
        $statusParts = $serviceStatus -split "`t"
        $status = $statusParts[0]
        $running = $statusParts[1]
        $desired = $statusParts[2]
        
        Write-Host "  Status: $status, Running: $running/$desired" -ForegroundColor Cyan
        
        if ($status -eq "ACTIVE" -and $running -eq $desired) {
            $stable = $true
            Write-Host "  ✅ Service is stable" -ForegroundColor Green
        }
    }
    
    if (-not $stable) {
        Start-Sleep -Seconds 10
        $attempt++
    }
}

if (-not $stable) {
    Write-Host "  ⚠️  Service may still be updating. Check AWS Console." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Check ECS logs: aws logs tail /ecs/validator-service --follow --region $REGION" -ForegroundColor White
Write-Host "  2. Look for debug messages about frontend paths" -ForegroundColor White
Write-Host "  3. Test CloudFront: https://d3evfv0v7o5aro.cloudfront.net" -ForegroundColor White
Write-Host ""








