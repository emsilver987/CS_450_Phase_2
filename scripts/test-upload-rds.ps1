# Test upload-rds-url endpoint
$API_BASE = "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod"
$MODEL_ID = "arnir0_Tiny-LLM"

# Step 1: Authenticate
Write-Host "Authenticating..."
# Read auth credentials from auth.json file (if it exists)
$authJsonPath = Join-Path $PSScriptRoot "..\auth.json"
if (Test-Path $authJsonPath) {
  $authBody = Get-Content $authJsonPath -Raw | ConvertFrom-Json | ConvertTo-Json
  Write-Host "Using credentials from auth.json"
} else {
  # Fallback to hardcoded credentials
  $authBody = @{
    user = @{
      name = "ece30861defaultadminuser"
      is_admin = $true
    }
    secret = @{
      password = "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
    }
  } | ConvertTo-Json
  Write-Host "Using hardcoded credentials (auth.json not found)"
}

$TOKEN = (Invoke-WebRequest -Uri "$API_BASE/authenticate" `
  -Method PUT `
  -ContentType "application/json" `
  -Body $authBody).Content.Trim('"').Trim("'")

Write-Host "Token obtained: $($TOKEN.Substring(0, [Math]::Min(30, $TOKEN.Length)))..."

# Step 2: Test endpoint
Write-Host "`nTesting upload-rds-url endpoint..."
$testUrl = "$API_BASE/artifact/model/$MODEL_ID/upload-rds-url?version=main&path_prefix=performance"
$headers = @{"X-Authorization" = $TOKEN}

try {
  $response = Invoke-RestMethod -Uri $testUrl -Method GET -Headers $headers
  Write-Host "✓ Success! Endpoint is deployed and working." -ForegroundColor Green
  Write-Host "Response:"
  $response | ConvertTo-Json -Depth 10
} catch {
  $statusCode = $null
  $responseBody = ""
  
  # Handle different exception types
  if ($_.Exception.Response) {
    $statusCode = $_.Exception.Response.StatusCode.value__
    
    # Try to read response body
    try {
      $stream = $_.Exception.Response.GetResponseStream()
      $reader = New-Object System.IO.StreamReader($stream)
      $responseBody = $reader.ReadToEnd()
      $reader.Close()
      $stream.Close()
    } catch {
      # If we can't read the stream, try alternative method
      try {
        $responseBody = $_.Exception.Response | ConvertTo-Json
      } catch {
        $responseBody = "Unable to read response body"
      }
    }
  } elseif ($_.Exception -is [System.Net.WebException]) {
    $statusCode = [int]($_.Exception.Response.StatusCode)
    try {
      $stream = $_.Exception.Response.GetResponseStream()
      $reader = New-Object System.IO.StreamReader($stream)
      $responseBody = $reader.ReadToEnd()
      $reader.Close()
      $stream.Close()
    } catch {
      $responseBody = $_.Exception.Message
    }
  }
  
  Write-Host "✗ Error: HTTP $statusCode" -ForegroundColor Red
  Write-Host "Message: $($_.Exception.Message)"
  
  if ($responseBody) {
    Write-Host "Response: $responseBody"
    
    if ($statusCode -eq 403 -and ($responseBody -like "*Missing Authentication Token*" -or $responseBody -like "*message*Missing Authentication Token*")) {
      Write-Host "`n⚠ This usually means the endpoint is not deployed to API Gateway yet." -ForegroundColor Yellow
      Write-Host "The endpoint IS configured in Terraform (infra/modules/api-gateway/main.tf)" -ForegroundColor Yellow
      Write-Host "To deploy, run: cd infra && terraform apply" -ForegroundColor Yellow
    }
  }
}