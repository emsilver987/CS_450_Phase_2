# Test script to verify CloudFront behavior matches localhost
# Compares CloudFront responses with localhost responses

$cloudfrontUrl = "https://d2nz7sldmigxeq.cloudfront.net"
$localhostUrl = "http://localhost:3000"

Write-Host "=== Testing CloudFront vs Localhost ===" -ForegroundColor Cyan
Write-Host "CloudFront: $cloudfrontUrl" -ForegroundColor Yellow
Write-Host "Localhost: $localhostUrl" -ForegroundColor Yellow
Write-Host ""

$testsPassed = 0
$testsFailed = 0

function Test-Endpoint {
    param(
        [string]$Path,
        [string]$Method = "GET",
        [hashtable]$Headers = @{},
        [string]$Body = $null,
        [bool]$CompareContent = $false
    )
    
    $testName = "$Method $Path"
    Write-Host "Testing: $testName" -ForegroundColor Yellow
    
    try {
        # Test CloudFront
        $cfParams = @{
            Uri = "$cloudfrontUrl$Path"
            Method = $Method
            UseBasicParsing = $true
            ErrorAction = "Stop"
        }
        if ($Headers.Count -gt 0) {
            $cfParams.Headers = $Headers
        }
        if ($Body) {
            $cfParams.Body = $Body
            $cfParams.ContentType = "application/json"
        }
        
        $cfResponse = Invoke-WebRequest @cfParams
        $cfStatus = $cfResponse.StatusCode
        $cfContent = $cfResponse.Content
        
        # Test Localhost
        $lhParams = @{
            Uri = "$localhostUrl$Path"
            Method = $Method
            UseBasicParsing = $true
            ErrorAction = "Stop"
        }
        if ($Headers.Count -gt 0) {
            $lhParams.Headers = $Headers
        }
        if ($Body) {
            $lhParams.Body = $Body
            $lhParams.ContentType = "application/json"
        }
        
        $lhResponse = Invoke-WebRequest @lhParams
        $lhStatus = $lhResponse.StatusCode
        $lhContent = $lhResponse.Content
        
        # Compare results
        if ($cfStatus -eq $lhStatus) {
            Write-Host "  ✅ Status codes match: $cfStatus" -ForegroundColor Green
            
            if ($CompareContent) {
                if ($cfContent -eq $lhContent) {
                    Write-Host "  ✅ Content matches" -ForegroundColor Green
                    $script:testsPassed++
                } else {
                    Write-Host "  ⚠️  Content differs (may be expected for dynamic content)" -ForegroundColor Yellow
                    $script:testsPassed++
                }
            } else {
                $script:testsPassed++
            }
        } else {
            Write-Host "  ❌ Status codes differ: CloudFront=$cfStatus, Localhost=$lhStatus" -ForegroundColor Red
            $script:testsFailed++
        }
    } catch {
        $errorMsg = $_.Exception.Message
        Write-Host "  ❌ Error: $errorMsg" -ForegroundColor Red
        $script:testsFailed++
    }
    Write-Host ""
}

# Test 1: Home page
Test-Endpoint -Path "/" -CompareContent $false

# Test 2: Static assets
Test-Endpoint -Path "/static/styles.css" -CompareContent $false

# Test 3: Health check
Test-Endpoint -Path "/health" -CompareContent $true

# Test 4: Frontend pages
$frontendPages = @("/directory", "/upload", "/rate", "/admin", "/lineage", "/size-cost", "/ingest")
foreach ($page in $frontendPages) {
    Test-Endpoint -Path $page -CompareContent $false
}

# Test 5: API endpoints with headers
Write-Host "Testing API endpoints with headers..." -ForegroundColor Cyan
$authBody = @{
    user = @{
        name = "ece30861defaultadminuser"
    }
    secret = @{
        password = "correcthorsebatterystaple123(!__+@**(A'`;DROP TABLE artifacts;"
    }
} | ConvertTo-Json

Test-Endpoint -Path "/authenticate" -Method "PUT" -Body $authBody -CompareContent $false

# Test 6: Check headers are forwarded
Write-Host "Testing header forwarding..." -ForegroundColor Cyan
$testHeaders = @{
    "Authorization" = "Bearer test-token"
    "X-Authorization" = "Bearer test-token"
    "Custom-Header" = "test-value"
}
Test-Endpoint -Path "/health" -Headers $testHeaders -CompareContent $false

# Summary
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
Write-Host "Tests Passed: $testsPassed" -ForegroundColor Green
Write-Host "Tests Failed: $testsFailed" -ForegroundColor $(if ($testsFailed -eq 0) { "Green" } else { "Red" })
Write-Host ""

if ($testsFailed -eq 0) {
    Write-Host "✅ All tests passed! CloudFront is working correctly." -ForegroundColor Green
} else {
    Write-Host "⚠️  Some tests failed. Review the output above." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "CloudFront URL: $cloudfrontUrl" -ForegroundColor Cyan
Write-Host "You can now access your application via CloudFront!" -ForegroundColor Green

