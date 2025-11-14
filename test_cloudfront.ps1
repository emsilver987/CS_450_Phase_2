# Test CloudFront Endpoints
# CloudFront URL: https://d2zjt0e91sz00o.cloudfront.net

$CLOUDFRONT_URL = "https://d2zjt0e91sz00o.cloudfront.net"

Write-Host "=== Testing CloudFront Distribution ===" -ForegroundColor Cyan
Write-Host "CloudFront URL: $CLOUDFRONT_URL" -ForegroundColor Yellow
Write-Host "Distribution ID: E27BNF4LOA341W" -ForegroundColor Yellow
Write-Host ""

function Test-Endpoint {
    param(
        [string]$Path,
        [string]$Description,
        [string]$Method = "GET"
    )
    
    $url = "$CLOUDFRONT_URL$Path"
    Write-Host "Testing: $Description" -ForegroundColor Yellow
    Write-Host "  URL: $url" -ForegroundColor Gray
    Write-Host "  Method: $Method" -ForegroundColor Gray
    
    try {
        if ($Method -eq "GET") {
            $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        } else {
            $response = Invoke-WebRequest -Uri $url -Method $Method -UseBasicParsing -TimeoutSec 15 -ErrorAction Stop
        }
        
        $status = $response.StatusCode
        $contentLength = $response.Content.Length
        $contentType = $response.Headers["Content-Type"]
        
        if ($status -eq 200) {
            Write-Host "  ✅ Status: $status" -ForegroundColor Green
            Write-Host "  ✅ Content-Type: $contentType" -ForegroundColor Green
            Write-Host "  ✅ Content Length: $contentLength bytes" -ForegroundColor Green
            
            # Check if it's HTML (frontend page)
            if ($contentType -like "*text/html*") {
                if ($response.Content -match "<!DOCTYPE|<html") {
                    Write-Host "  ✅ Valid HTML content" -ForegroundColor Green
                }
            }
            
            return $true
        } else {
            Write-Host "  ⚠️  Status: $status (expected 200)" -ForegroundColor Yellow
            return $false
        }
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $errorMessage = $_.Exception.Message
        
        if ($statusCode) {
            Write-Host "  ❌ Status: $statusCode" -ForegroundColor Red
            Write-Host "  ❌ Error: $errorMessage" -ForegroundColor Red
        } else {
            Write-Host "  ❌ Error: $errorMessage" -ForegroundColor Red
        }
        
        return $false
    }
    
    Write-Host ""
}

# Test 1: Health Endpoint
Write-Host "1. Testing Health Endpoint" -ForegroundColor Cyan
Write-Host ""
Test-Endpoint -Path "/health" -Description "Health Check"

# Test 2: Frontend Pages
Write-Host ""
Write-Host "2. Testing Frontend Pages" -ForegroundColor Cyan
Write-Host ""
Test-Endpoint -Path "/" -Description "Home Page"
Test-Endpoint -Path "/directory" -Description "Directory Page"
Test-Endpoint -Path "/upload" -Description "Upload Page"
Test-Endpoint -Path "/rate" -Description "Rate Page"
Test-Endpoint -Path "/admin" -Description "Admin Page"

# Test 3: Static Assets
Write-Host ""
Write-Host "3. Testing Static Assets" -ForegroundColor Cyan
Write-Host ""
Test-Endpoint -Path "/static/styles.css" -Description "CSS Stylesheet"

# Test 4: API Endpoints
Write-Host ""
Write-Host "4. Testing API Endpoints" -ForegroundColor Cyan
Write-Host ""
Test-Endpoint -Path "/api/hello" -Description "API Hello (via API Gateway)"

# Test 5: Additional Routes
Write-Host ""
Write-Host "5. Testing Additional Routes" -ForegroundColor Cyan
Write-Host ""
Test-Endpoint -Path "/lineage" -Description "Lineage Page"
Test-Endpoint -Path "/size-cost" -Description "Size Cost Page"
Test-Endpoint -Path "/ingest" -Description "Ingest Page"

# Summary
Write-Host ""
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "CloudFront URL: $CLOUDFRONT_URL" -ForegroundColor White
Write-Host "Distribution ID: E27BNF4LOA341W" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Open $CLOUDFRONT_URL in your browser" -ForegroundColor White
Write-Host "  2. Test navigation between pages" -ForegroundColor White
Write-Host "  3. Verify styling and functionality" -ForegroundColor White
Write-Host "  4. Check CloudWatch metrics for performance" -ForegroundColor White
Write-Host ""



