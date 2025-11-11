# Build and Run Docker Container Script

Write-Host "=== Building and Running Docker Container ===" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "1. Checking Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] Docker is available" -ForegroundColor Green
        Write-Host "        $dockerVersion" -ForegroundColor Gray
    } else {
        Write-Host "   [FAIL] Docker is not available" -ForegroundColor Red
        Write-Host "   Please start Docker Desktop" -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "   [FAIL] Docker is not installed or not running" -ForegroundColor Red
    Write-Host "   Please install Docker Desktop and start it" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Stop and remove existing container if it exists
Write-Host "2. Stopping existing containers..." -ForegroundColor Yellow
docker-compose down 2>&1 | Out-Null
Write-Host "   [OK] Existing containers stopped" -ForegroundColor Green
Write-Host ""

# Build the Docker image
Write-Host "3. Building Docker image..." -ForegroundColor Yellow
Write-Host "   This may take a few minutes on first build..." -ForegroundColor Gray
docker-compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "   [FAIL] Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "   [OK] Docker image built successfully" -ForegroundColor Green
Write-Host ""

# Check AWS credentials
Write-Host "4. Checking AWS credentials..." -ForegroundColor Yellow
try {
    $identity = aws sts get-caller-identity 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] AWS credentials are configured" -ForegroundColor Green
        Write-Host "   Note: Container will use host AWS credentials via volume mount" -ForegroundColor Gray
    } else {
        Write-Host "   [WARN] AWS credentials not configured" -ForegroundColor Yellow
        Write-Host "   Container may not be able to access AWS services" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   [WARN] Could not check AWS credentials" -ForegroundColor Yellow
}
Write-Host ""

# Run the container
Write-Host "5. Starting Docker container..." -ForegroundColor Yellow
Write-Host "   Server will be available at: http://localhost:3000" -ForegroundColor Cyan
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

# Mount AWS credentials directory if it exists
$awsCredsPath = "$env:USERPROFILE\.aws"
if (Test-Path $awsCredsPath) {
    Write-Host "   Mounting AWS credentials from: $awsCredsPath" -ForegroundColor Gray
    docker-compose up --build
} else {
    Write-Host "   AWS credentials directory not found at: $awsCredsPath" -ForegroundColor Yellow
    Write-Host "   Container will use environment variables only" -ForegroundColor Gray
    docker-compose up --build
}


