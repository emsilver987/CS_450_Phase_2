# Test Localhost API Script
# This script tests the API endpoints running on localhost:3000

$baseUrl = "http://localhost:3000"
$testResults = @()

Write-Host "=== Testing Localhost API ===" -ForegroundColor Cyan
Write-Host "Base URL: $baseUrl" -ForegroundColor Gray
Write-Host "Working Directory: $(Get-Location)" -ForegroundColor Gray
Write-Host ""

# Function to test an endpoint
function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method = "GET",
        [string]$Path,
        [hashtable]$Headers = @{},
        [object]$Body = $null,
        [int]$ExpectedStatus = 200
    )
    
    $url = "$baseUrl$Path"
    $result = @{
        Name = $Name
        Path = $Path
        Method = $Method
        Status = "PENDING"
        StatusCode = $null
        Message = ""
        Success = $false
    }
    
    try {
        $params = @{
            Uri = $url
            Method = $Method
            Headers = $Headers
            TimeoutSec = 10
            UseBasicParsing = $true
            ErrorAction = "Stop"
        }
        
        if ($Body) {
            if ($Body -is [hashtable] -or $Body -is [PSCustomObject]) {
                $params["Body"] = ($Body | ConvertTo-Json -Depth 10)
                $params["ContentType"] = "application/json"
            } else {
                $params["Body"] = $Body
            }
        }
        
        $response = Invoke-WebRequest @params
        $result.StatusCode = $response.StatusCode
        $result.Success = ($response.StatusCode -eq $ExpectedStatus)
        $result.Status = if ($result.Success) { "PASS" } else { "UNEXPECTED STATUS" }
        $result.Message = "Status: $($response.StatusCode)"
        
        # Try to parse JSON response
        try {
            $jsonContent = $response.Content | ConvertFrom-Json
            $result.Message += " | Response: " + ($jsonContent | ConvertTo-Json -Compress -Depth 2)
        } catch {
            $result.Message += " | Response length: $($response.Content.Length) bytes"
        }
        
    } catch {
        $result.Status = "FAIL"
        if ($_.Exception.Response) {
            $result.StatusCode = $_.Exception.Response.StatusCode.value__
            $result.Message = "Error: $($_.Exception.Message) (Status: $($result.StatusCode))"
        } else {
            $result.Message = "Error: $($_.Exception.Message)"
        }
        $result.Success = $false
    }
    
    return $result
}

# Test 1: Health Check
Write-Host "1. Testing Health Endpoint..." -ForegroundColor Yellow
$healthResult = Test-Endpoint -Name "Health Check" -Path "/health"
$testResults += $healthResult
$color = if ($healthResult.Success) { "Green" } else { "Red" }
Write-Host "   [$($healthResult.Status)] - $($healthResult.Message)" -ForegroundColor $color
Write-Host ""

# Test 2: Health Components
Write-Host "2. Testing Health Components..." -ForegroundColor Yellow
$healthCompResult = Test-Endpoint -Name "Health Components" -Path "/health/components"
$testResults += $healthCompResult
$color = if ($healthCompResult.Success) { "Green" } else { "Red" }
Write-Host "   [$($healthCompResult.Status)] - $($healthCompResult.Message)" -ForegroundColor $color
Write-Host ""

# Test 3: Tracks Endpoint
Write-Host "3. Testing Tracks Endpoint..." -ForegroundColor Yellow
$tracksResult = Test-Endpoint -Name "Tracks" -Path "/tracks"
$testResults += $tracksResult
$color = if ($tracksResult.Success) { "Green" } else { "Red" }
Write-Host "   [$($tracksResult.Status)] - $($tracksResult.Message)" -ForegroundColor $color
Write-Host ""

# Test 4: API Hello (if exists)
Write-Host "4. Testing API Hello..." -ForegroundColor Yellow
$apiHelloResult = Test-Endpoint -Name "API Hello" -Path "/api/hello"
$testResults += $apiHelloResult
$color = if ($apiHelloResult.Success) { "Green" } else { "Yellow" }
Write-Host "   [$($apiHelloResult.Status)] - $($apiHelloResult.Message)" -ForegroundColor $color
Write-Host ""

# Test 5: Static Files (CSS)
Write-Host "5. Testing Static Files..." -ForegroundColor Yellow
$staticResult = Test-Endpoint -Name "Static CSS" -Path "/static/styles.css"
$testResults += $staticResult
$color = if ($staticResult.Success) { "Green" } else { "Yellow" }
Write-Host "   [$($staticResult.Status)] - $($staticResult.Message)" -ForegroundColor $color
Write-Host ""

# Test 6: Frontend Pages
Write-Host "6. Testing Frontend Pages..." -ForegroundColor Yellow
$frontendPages = @("/", "/directory", "/upload", "/rate", "/admin")
foreach ($page in $frontendPages) {
    $pageResult = Test-Endpoint -Name "Frontend: $page" -Path $page -ExpectedStatus 200
    $testResults += $pageResult
    $color = if ($pageResult.Success) { "Green" } elseif ($pageResult.StatusCode -eq 404) { "Yellow" } else { "Red" }
    Write-Host "   [$($pageResult.Status)] - $page - $($pageResult.Message)" -ForegroundColor $color
}
Write-Host ""

# Test 7: Authenticate Endpoint (PUT) - with test credentials
Write-Host "7. Testing Authenticate Endpoint..." -ForegroundColor Yellow
$authBody = @{
    user = @{
        name = "testuser"
        is_admin = $false
    }
    secret = @{
        password = "testpass"
    }
}
$authResult = Test-Endpoint -Name "Authenticate (test)" -Method "PUT" -Path "/authenticate" -Body $authBody -ExpectedStatus 200
$testResults += $authResult
$color = if ($authResult.Success) { "Green" } else { "Yellow" }
Write-Host "   [$($authResult.Status)] - $($authResult.Message)" -ForegroundColor $color
Write-Host ""

# Test 8: Authenticate with valid credentials from auth.json
Write-Host "8. Testing Authenticate with auth.json..." -ForegroundColor Yellow
if (Test-Path "auth.json") {
    $authData = Get-Content "auth.json" | ConvertFrom-Json
    $authValidResult = Test-Endpoint -Name "Authenticate (valid)" -Method "PUT" -Path "/authenticate" -Body $authData -ExpectedStatus 200
    $testResults += $authValidResult
    $color = if ($authValidResult.Success) { "Green" } else { "Yellow" }
    Write-Host "   [$($authValidResult.Status)] - $($authValidResult.Message)" -ForegroundColor $color
    
    # If successful, extract token for future tests
    if ($authValidResult.Success -and $authValidResult.Message -match "token") {
        Write-Host "   Token received successfully!" -ForegroundColor Green
    }
} else {
    Write-Host "   [SKIP] - auth.json not found" -ForegroundColor Gray
}
Write-Host ""

# Summary
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
$passed = ($testResults | Where-Object { $_.Success }).Count
$failed = ($testResults | Where-Object { -not $_.Success }).Count
$total = $testResults.Count

Write-Host "Total Tests: $total" -ForegroundColor White
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed/Warnings: $failed" -ForegroundColor $(if ($failed -gt 0) { "Yellow" } else { "Green" })
Write-Host ""

if ($failed -gt 0) {
    Write-Host "Failed/Warning Tests:" -ForegroundColor Yellow
    $testResults | Where-Object { -not $_.Success } | ForEach-Object {
        Write-Host "  - $($_.Name) ($($_.Path)): $($_.Message)" -ForegroundColor Yellow
    }
    Write-Host ""
}

# Check if server is running
if ($failed -eq $total) {
    Write-Host "WARNING: All tests failed!" -ForegroundColor Red
    Write-Host "The server may not be running. Start it with:" -ForegroundColor Yellow
    Write-Host "  python -m uvicorn src.entrypoint:app --host 0.0.0.0 --port 3000 --reload" -ForegroundColor Green
    Write-Host ""
}

Write-Host "=== Test Complete ===" -ForegroundColor Cyan


