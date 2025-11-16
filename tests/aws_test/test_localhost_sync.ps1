# Test script to verify localhost behavior matches CloudFront expectations
# Run this after starting the localhost server

$baseUrl = "http://localhost:3000"

Write-Host "=== Testing Localhost Server ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Home page
Write-Host "1. Testing home page..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Home page loads (Status: $($response.StatusCode))" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Home page failed (Status: $($response.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Home page error: $_" -ForegroundColor Red
}

# Test 2: Static assets
Write-Host "2. Testing static assets..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/static/styles.css" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Static CSS loads (Status: $($response.StatusCode), Content-Type: $($response.Headers['Content-Type']))" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Static CSS failed (Status: $($response.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Static CSS error: $_" -ForegroundColor Red
}

# Test 3: Health check
Write-Host "3. Testing health check..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$baseUrl/health" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Health check works (Status: $($response.StatusCode))" -ForegroundColor Green
        Write-Host "   Response: $($response.Content)" -ForegroundColor Gray
    } else {
        Write-Host "   ❌ Health check failed (Status: $($response.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Health check error: $_" -ForegroundColor Red
}

# Test 4: Frontend pages
Write-Host "4. Testing frontend pages..." -ForegroundColor Yellow
$pages = @("/directory", "/upload", "/rate", "/admin", "/lineage", "/size-cost", "/ingest", "/license-check")
foreach ($page in $pages) {
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl$page" -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "   ✅ $page loads (Status: $($response.StatusCode))" -ForegroundColor Green
        } else {
            Write-Host "   ❌ $page failed (Status: $($response.StatusCode))" -ForegroundColor Red
        }
    } catch {
        Write-Host "   ❌ $page error: $_" -ForegroundColor Red
    }
}

# Test 5: API endpoints (with headers)
Write-Host "5. Testing API endpoints..." -ForegroundColor Yellow
try {
    # Test authentication endpoint
    $authBody = @{
        user = @{
            name = "ece30861defaultadminuser"
        }
        secret = @{
            password = "correcthorsebatterystaple123(!__+@**(A'`;DROP TABLE artifacts;"
        }
    } | ConvertTo-Json
    
    $response = Invoke-WebRequest -Uri "$baseUrl/authenticate" -Method PUT -Body $authBody -ContentType "application/json" -UseBasicParsing
    if ($response.StatusCode -eq 200) {
        Write-Host "   ✅ Authentication endpoint works (Status: $($response.StatusCode))" -ForegroundColor Green
        Write-Host "   Token: $($response.Content.Substring(0, [Math]::Min(50, $response.Content.Length)))..." -ForegroundColor Gray
    } else {
        Write-Host "   ❌ Authentication failed (Status: $($response.StatusCode))" -ForegroundColor Red
    }
} catch {
    Write-Host "   ❌ Authentication error: $_" -ForegroundColor Red
}

# Test 6: Check headers are forwarded
Write-Host "6. Testing header forwarding..." -ForegroundColor Yellow
try {
    $headers = @{
        "Authorization" = "Bearer test-token"
        "X-Authorization" = "Bearer test-token"
        "Custom-Header" = "test-value"
    }
    $response = Invoke-WebRequest -Uri "$baseUrl/health" -Headers $headers -UseBasicParsing
    Write-Host "   ✅ Headers can be sent (Status: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Header test error: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Deploy CloudFront configuration: cd infra/envs/dev && terraform apply" -ForegroundColor White
Write-Host "2. Test CloudFront URL with the same tests above" -ForegroundColor White
Write-Host "3. Compare results to ensure they match" -ForegroundColor White

