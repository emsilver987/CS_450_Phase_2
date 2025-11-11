# Comprehensive Test Script for Localhost, AWS Services, and CloudFront
# Usage: .\test_all_services.ps1

$ErrorActionPreference = "Continue"
$script:TestResults = @()

function Write-TestResult {
    param(
        [string]$Service,
        [string]$Test,
        [string]$Status,
        [string]$Details = ""
    )
    $result = [PSCustomObject]@{
        Service = $Service
        Test = $Test
        Status = $Status
        Details = $Details
        Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    }
    $script:TestResults += $result
    
    $color = switch ($Status) {
        "PASS" { "Green" }
        "FAIL" { "Red" }
        "WARN" { "Yellow" }
        default { "White" }
    }
    Write-Host "[$Status] $Service - $Test" -ForegroundColor $color
    if ($Details) {
        Write-Host "  → $Details" -ForegroundColor Gray
    }
}

function Test-Localhost {
    Write-Host "`n=== Testing Localhost (http://localhost:3000) ===" -ForegroundColor Cyan
    
    $baseUrl = "http://localhost:3000"
    
    # Test 1: Check if service is running
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/health" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-TestResult "Localhost" "Service Running" "PASS" "Health endpoint responded"
        } else {
            Write-TestResult "Localhost" "Service Running" "FAIL" "Health endpoint returned status $($response.StatusCode)"
        }
    } catch {
        Write-TestResult "Localhost" "Service Running" "FAIL" "Could not connect: $($_.Exception.Message)"
        Write-Host "  ⚠ Make sure the app is running: python -m uvicorn src.entrypoint:app --host 0.0.0.0 --port 3000" -ForegroundColor Yellow
        return
    }
    
    # Test 2: Root endpoint
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-TestResult "Localhost" "Root Endpoint" "PASS" "Status: $($response.StatusCode)"
    } catch {
        Write-TestResult "Localhost" "Root Endpoint" "FAIL" $_.Exception.Message
    }
    
    # Test 3: API Hello endpoint
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/api/hello" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        $content = $response.Content | ConvertFrom-Json
        Write-TestResult "Localhost" "API Hello" "PASS" "Response: $($content.message)"
    } catch {
        Write-TestResult "Localhost" "API Hello" "FAIL" $_.Exception.Message
    }
    
    # Test 4: Static files
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/static/styles.css" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-TestResult "Localhost" "Static Files" "PASS" "CSS file accessible"
    } catch {
        Write-TestResult "Localhost" "Static Files" "WARN" "CSS file not found (may be expected)"
    }
    
    # Test 5: Frontend pages
    $frontendPages = @("/", "/directory", "/upload", "/rate", "/admin")
    foreach ($page in $frontendPages) {
        try {
            $response = Invoke-WebRequest -Uri "$baseUrl$page" -Method GET -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-TestResult "Localhost" "Frontend: $page" "PASS" "Page loaded successfully"
            } else {
                Write-TestResult "Localhost" "Frontend: $page" "FAIL" "Status: $($response.StatusCode)"
            }
        } catch {
            Write-TestResult "Localhost" "Frontend: $page" "FAIL" $_.Exception.Message
        }
    }
}

function Test-AWSServices {
    Write-Host "`n=== Testing AWS Services ===" -ForegroundColor Cyan
    
    # Get Terraform outputs
    Push-Location "infra/envs/dev"
    try {
        Write-Host "Fetching Terraform outputs..." -ForegroundColor Yellow
        $tfOutput = terraform output -json 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-TestResult "AWS" "Terraform Outputs" "FAIL" "Could not get Terraform outputs. Run 'terraform init' and 'terraform apply' first."
            Pop-Location
            return
        }
        
        $outputs = $tfOutput | ConvertFrom-Json
        
        # Get ALB URL
        $albUrl = $outputs.validator_service_url.value
        if (-not $albUrl) {
            Write-TestResult "AWS" "ALB URL" "FAIL" "ALB URL not found in Terraform outputs"
            Pop-Location
            return
        }
        Write-Host "  ALB URL: $albUrl" -ForegroundColor Gray
        
        # Get API Gateway URL
        $apiGatewayUrl = $null
        if ($outputs.api_gateway_url) {
            $apiGatewayUrl = $outputs.api_gateway_url.value
            Write-Host "  API Gateway URL: $apiGatewayUrl" -ForegroundColor Gray
        }
        
        # Get CloudFront URL
        $cloudfrontUrl = $null
        if ($outputs.cloudfront_url) {
            $cloudfrontUrl = $outputs.cloudfront_url.value
            Write-Host "  CloudFront URL: $cloudfrontUrl" -ForegroundColor Gray
        }
        
        Pop-Location
        
        # Test ALB
        Write-Host "`n--- Testing ALB (Application Load Balancer) ---" -ForegroundColor Yellow
        try {
            $response = Invoke-WebRequest -Uri "$albUrl/health" -Method GET -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-TestResult "AWS ALB" "Health Check" "PASS" "Status: $($response.StatusCode)"
            } else {
                Write-TestResult "AWS ALB" "Health Check" "FAIL" "Status: $($response.StatusCode)"
            }
        } catch {
            Write-TestResult "AWS ALB" "Health Check" "FAIL" $_.Exception.Message
        }
        
        try {
            $response = Invoke-WebRequest -Uri "$albUrl/" -Method GET -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
            Write-TestResult "AWS ALB" "Root Endpoint" "PASS" "Status: $($response.StatusCode)"
        } catch {
            Write-TestResult "AWS ALB" "Root Endpoint" "FAIL" $_.Exception.Message
        }
        
        # Test API Gateway
        if ($apiGatewayUrl) {
            Write-Host "`n--- Testing API Gateway ---" -ForegroundColor Yellow
            try {
                $response = Invoke-WebRequest -Uri "$apiGatewayUrl/health" -Method GET -TimeoutSec 10 -UseBasicParsing -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    Write-TestResult "AWS API Gateway" "Health Check" "PASS" "Status: $($response.StatusCode)"
                } else {
                    Write-TestResult "AWS API Gateway" "Health Check" "FAIL" "Status: $($response.StatusCode)"
                }
            } catch {
                Write-TestResult "AWS API Gateway" "Health Check" "FAIL" $_.Exception.Message
            }
        } else {
            Write-TestResult "AWS API Gateway" "Configuration" "WARN" "API Gateway URL not found in outputs"
        }
        
        # Test ECS Service
        Write-Host "`n--- Testing ECS Service ---" -ForegroundColor Yellow
        try {
            $clusterArn = $outputs.validator_cluster_arn.value
            if ($clusterArn) {
                $clusterName = $clusterArn.Split("/")[-1]
                $services = aws ecs list-services --cluster $clusterName --region us-east-1 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-TestResult "AWS ECS" "Service Status" "PASS" "Cluster: $clusterName"
                } else {
                    Write-TestResult "AWS ECS" "Service Status" "WARN" "Could not list services: $services"
                }
            } else {
                Write-TestResult "AWS ECS" "Service Status" "WARN" "Cluster ARN not found"
            }
        } catch {
            Write-TestResult "AWS ECS" "Service Status" "WARN" $_.Exception.Message
        }
        
        # Test S3
        Write-Host "`n--- Testing S3 ---" -ForegroundColor Yellow
        try {
            $bucketName = $outputs.artifacts_bucket.value
            if ($bucketName) {
                $s3Check = aws s3 ls s3://$bucketName --region us-east-1 2>&1
                if ($LASTEXITCODE -eq 0) {
                    Write-TestResult "AWS S3" "Bucket Access" "PASS" "Bucket: $bucketName"
                } else {
                    Write-TestResult "AWS S3" "Bucket Access" "FAIL" "Could not access bucket: $s3Check"
                }
            } else {
                Write-TestResult "AWS S3" "Bucket Access" "WARN" "Bucket name not found"
            }
        } catch {
            Write-TestResult "AWS S3" "Bucket Access" "WARN" $_.Exception.Message
        }
        
        # Test DynamoDB
        Write-Host "`n--- Testing DynamoDB ---" -ForegroundColor Yellow
        try {
            $tables = $outputs.ddb_tables.value
            if ($tables) {
                $tableCount = ($tables.PSObject.Properties | Measure-Object).Count
                Write-TestResult "AWS DynamoDB" "Tables Configuration" "PASS" "$tableCount tables configured"
                
                # Try to list one table
                $firstTable = ($tables.PSObject.Properties | Select-Object -First 1).Name
                if ($firstTable) {
                    $tableArn = $tables.$firstTable
                    $tableName = $tableArn.Split("/")[-1]
                    $ddbCheck = aws dynamodb describe-table --table-name $tableName --region us-east-1 2>&1
                    if ($LASTEXITCODE -eq 0) {
                        Write-TestResult "AWS DynamoDB" "Table Access" "PASS" "Table '$tableName' accessible"
                    } else {
                        Write-TestResult "AWS DynamoDB" "Table Access" "WARN" "Could not access table: $ddbCheck"
                    }
                }
            } else {
                Write-TestResult "AWS DynamoDB" "Tables Configuration" "WARN" "Tables not found in outputs"
            }
        } catch {
            Write-TestResult "AWS DynamoDB" "Table Access" "WARN" $_.Exception.Message
        }
        
    } catch {
        Write-TestResult "AWS" "Configuration" "FAIL" "Error: $($_.Exception.Message)"
        Pop-Location
    }
}

function Test-CloudFront {
    Write-Host "`n=== Testing CloudFront ===" -ForegroundColor Cyan
    
    Push-Location "infra/envs/dev"
    try {
        $tfOutput = terraform output -json 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-TestResult "CloudFront" "Terraform Outputs" "FAIL" "Could not get Terraform outputs"
            Pop-Location
            return
        }
        
        $outputs = $tfOutput | ConvertFrom-Json
        $cloudfrontUrl = $null
        
        if ($outputs.cloudfront_url) {
            $cloudfrontUrl = $outputs.cloudfront_url.value
        } elseif ($outputs.cloudfront_domain_name) {
            $cloudfrontUrl = "https://$($outputs.cloudfront_domain_name.value)"
        }
        
        Pop-Location
        
        if (-not $cloudfrontUrl) {
            Write-TestResult "CloudFront" "Configuration" "WARN" "CloudFront URL not found. Run 'terraform apply' to deploy CloudFront."
            return
        }
        
        Write-Host "  CloudFront URL: $cloudfrontUrl" -ForegroundColor Gray
        
        # Test CloudFront root
        try {
            $response = Invoke-WebRequest -Uri "$cloudfrontUrl/" -Method GET -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-TestResult "CloudFront" "Root Endpoint" "PASS" "Status: $($response.StatusCode)"
            } else {
                Write-TestResult "CloudFront" "Root Endpoint" "FAIL" "Status: $($response.StatusCode)"
            }
        } catch {
            Write-TestResult "CloudFront" "Root Endpoint" "FAIL" $_.Exception.Message
        }
        
        # Test CloudFront health
        try {
            $response = Invoke-WebRequest -Uri "$cloudfrontUrl/health" -Method GET -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-TestResult "CloudFront" "Health Check" "PASS" "Status: $($response.StatusCode)"
            } else {
                Write-TestResult "CloudFront" "Health Check" "FAIL" "Status: $($response.StatusCode)"
            }
        } catch {
            Write-TestResult "CloudFront" "Health Check" "FAIL" $_.Exception.Message
        }
        
        # Test CloudFront API
        try {
            $response = Invoke-WebRequest -Uri "$cloudfrontUrl/api/hello" -Method GET -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
            $content = $response.Content | ConvertFrom-Json
            Write-TestResult "CloudFront" "API Endpoint" "PASS" "Response: $($content.message)"
        } catch {
            Write-TestResult "CloudFront" "API Endpoint" "FAIL" $_.Exception.Message
        }
        
        # Test CloudFront static files
        try {
            $response = Invoke-WebRequest -Uri "$cloudfrontUrl/static/styles.css" -Method GET -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
            Write-TestResult "CloudFront" "Static Files" "PASS" "CSS file accessible"
        } catch {
            Write-TestResult "CloudFront" "Static Files" "WARN" "CSS file not found (may be expected)"
        }
        
        # Test CloudFront frontend pages
        $frontendPages = @("/directory", "/upload", "/rate")
        foreach ($page in $frontendPages) {
            try {
                $response = Invoke-WebRequest -Uri "$cloudfrontUrl$page" -Method GET -TimeoutSec 15 -UseBasicParsing -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    Write-TestResult "CloudFront" "Frontend: $page" "PASS" "Page loaded"
                } else {
                    Write-TestResult "CloudFront" "Frontend: $page" "FAIL" "Status: $($response.StatusCode)"
                }
            } catch {
                Write-TestResult "CloudFront" "Frontend: $page" "FAIL" $_.Exception.Message
            }
        }
        
    } catch {
        Write-TestResult "CloudFront" "Configuration" "FAIL" "Error: $($_.Exception.Message)"
        Pop-Location
    }
}

function Show-Summary {
    Write-Host "`n=== Test Summary ===" -ForegroundColor Cyan
    $total = $script:TestResults.Count
    $passed = ($script:TestResults | Where-Object { $_.Status -eq "PASS" }).Count
    $failed = ($script:TestResults | Where-Object { $_.Status -eq "FAIL" }).Count
    $warned = ($script:TestResults | Where-Object { $_.Status -eq "WARN" }).Count
    
    Write-Host "Total Tests: $total" -ForegroundColor White
    Write-Host "Passed: $passed" -ForegroundColor Green
    Write-Host "Failed: $failed" -ForegroundColor Red
    Write-Host "Warnings: $warned" -ForegroundColor Yellow
    
    if ($failed -gt 0) {
        Write-Host "`nFailed Tests:" -ForegroundColor Red
        $script:TestResults | Where-Object { $_.Status -eq "FAIL" } | ForEach-Object {
            Write-Host "  - $($_.Service): $($_.Test)" -ForegroundColor Red
        }
    }
    
    # Export results to file
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $resultsFile = "test_results_$timestamp.json"
    $script:TestResults | ConvertTo-Json -Depth 3 | Out-File $resultsFile
    Write-Host "`nResults saved to: $resultsFile" -ForegroundColor Gray
}

# Main execution
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Comprehensive Service Test Suite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Change to project directory
Set-Location "C:\Users\Taiwo\OneDrive\Documents\CSCI\debug\CS_450_Phase_2"

# Run tests
Test-Localhost
Test-AWSServices
Test-CloudFront

# Show summary
Show-Summary

Write-Host "`nTest suite completed!" -ForegroundColor Cyan


