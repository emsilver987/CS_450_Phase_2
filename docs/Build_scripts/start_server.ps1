# Start FastAPI Server with AWS Configuration
# This script sets the required environment variables and starts the server

Write-Host "=== Starting FastAPI Server ===" -ForegroundColor Cyan
Write-Host ""

# Set AWS Environment Variables
Write-Host "Setting AWS Environment Variables..." -ForegroundColor Yellow
$env:AWS_REGION = "us-east-1"
$env:AWS_ACCOUNT_ID = "838693051036"
$env:S3_ACCESS_POINT_NAME = "cs450-s3"

Write-Host "  ✅ AWS_REGION = $env:AWS_REGION" -ForegroundColor Green
Write-Host "  ✅ AWS_ACCOUNT_ID = $env:AWS_ACCOUNT_ID" -ForegroundColor Green
Write-Host "  ✅ S3_ACCESS_POINT_NAME = $env:S3_ACCESS_POINT_NAME" -ForegroundColor Green
Write-Host ""

# Verify AWS credentials
Write-Host "Verifying AWS credentials..." -ForegroundColor Yellow
try {
    $identity = aws sts get-caller-identity 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✅ AWS credentials verified" -ForegroundColor Green
    } else {
        Write-Host "  ❌ AWS credentials not configured" -ForegroundColor Red
        Write-Host "  Run: aws configure" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "  ❌ AWS CLI not available" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Starting FastAPI server on http://localhost:3000..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the server
python -m uvicorn src.entrypoint:app --host 0.0.0.0 --port 3000 --reload


