# -----------------------------
# CONFIGURATION & LOGGING
# -----------------------------
$LocalAPI = "http://127.0.0.2:8087"
$RemoteAPI = "https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod"
$API = $LocalAPI     # <- switch to $LocalAPI when testing locally

$AuthFile = ".\auth.json"   # should contain username/password JSON
$ModelURL = "https://huggingface.co/google-bert/bert-base-uncased"
$LogFile = Join-Path $PSScriptRoot "autograder_output.log"

if (Test-Path $LogFile) {
    Remove-Item $LogFile -Force
}

Start-Transcript -Path $LogFile -Append | Out-Null

function Write-Log {
    param([string]$Message)
    $timestamp = (Get-Date).ToString("s")
    Write-Host "[$timestamp] $Message"
}

function Invoke-LoggedRequest {
    param(
        [Parameter(Mandatory)]
        [string]$Method,
        [Parameter(Mandatory)]
        [string]$Uri,
        [Hashtable]$Headers,
        [string]$Body,
        [string]$ContentType = "application/json"
    )

    Write-Log "Request => $Method $Uri"
    if ($Body) {
        Write-Log "Request Body: $Body"
    }

    $webRequestParams = @{
        Method      = $Method
        Uri         = $Uri
        ErrorAction = 'Stop'
    }
    if ($Headers) { $webRequestParams["Headers"] = $Headers }
    if ($Body) { $webRequestParams["Body"] = $Body }
    if ($Body -and $ContentType) { $webRequestParams["ContentType"] = $ContentType }

    try {
        $response = Invoke-WebRequest @webRequestParams
        $content = $response.Content
        Write-Log "Response Status: $($response.StatusCode)"
        if ($content) {
            Write-Log "Response Body: $content"
        }
        return [pscustomobject]@{
            StatusCode  = [int]$response.StatusCode
            Content     = $content
            RawResponse = $response
        }
    } catch {
        $ex = $_.Exception
        if ($ex.Response -is [System.Net.HttpWebResponse]) {
            $errorResponse = $ex.Response
            $reader = New-Object System.IO.StreamReader($errorResponse.GetResponseStream())
            $content = $reader.ReadToEnd()
            $reader.Dispose()
            Write-Log "Response Status: $([int]$errorResponse.StatusCode)"
            if ($content) {
                Write-Log "Response Body: $content"
            }
            return [pscustomobject]@{
                StatusCode  = [int]$errorResponse.StatusCode
                Content     = $content
                RawResponse = $errorResponse
            }
        } else {
            Write-Log "Request error: $($ex.Message)"
            return $null
        }
    }
}

try {
    Write-Log "Starting autograder replication sequence."
    Write-Log "API endpoint: $API"

    # STEP 1: Unauthorized GET by name (expected 403)
    Write-Log "Simulating unauthenticated GET /artifact/byName"
    Invoke-LoggedRequest -Method GET -Uri "$API/artifact/byName/google-bert/bert-base-uncased"

    # STEP 2: Unauthorized GET model literal $id (expected 403)
    Write-Log "Simulating unauthenticated GET /artifact/model/\$id"
    $literalIdUri = "$API/artifact/model/`$id"
    Invoke-LoggedRequest -Method GET -Uri $literalIdUri

    # STEP 3: Unsupported GET /authenticate (expected 405)
    Write-Log "Simulating unsupported GET /authenticate"
    Invoke-LoggedRequest -Method GET -Uri "$API/authenticate"

    # STEP 4: Acquire token via PUT /authenticate
    Write-Log "Authenticating via PUT /authenticate"
    if (-not (Test-Path $AuthFile)) {
        throw "Auth file '$AuthFile' not found."
    }
    $authBody = Get-Content -Raw -Path $AuthFile
    $authResponse = Invoke-LoggedRequest -Method PUT -Uri "$API/authenticate" -Body $authBody
    $token = $null
    if ($authResponse -and $authResponse.Content) {
        $token = $authResponse.Content.Trim()
    }
    if (-not $token) {
        throw "Authentication failed — no token returned."
    }
    Write-Log "Token received: $token"

    $headers = @{
        "Content-Type"    = "application/json"
        "X-Authorization" = $token
    }

    # STEP 5: GET /artifact/byName with and without auth
    Write-Log "Repeat unauthenticated GET /artifact/byName to mirror logs"
    Invoke-LoggedRequest -Method GET -Uri "$API/artifact/byName/google-bert/bert-base-uncased"

    Write-Log "Authenticated GET /artifact/byName"
    Invoke-LoggedRequest -Method GET -Uri "$API/artifact/byName/google-bert/bert-base-uncased" -Headers $headers

    # STEP 6: Ingest primary model
    Write-Log "Ingesting primary model"
    $modelBody = @{ url = $ModelURL } | ConvertTo-Json -Compress
    $ingestResponse = Invoke-LoggedRequest -Method POST -Uri "$API/artifact/model" -Headers $headers -Body $modelBody

    $modelId = $null
    if ($ingestResponse -and $ingestResponse.Content) {
        try {
            $parsed = $ingestResponse.Content | ConvertFrom-Json
            $modelId = $parsed.metadata.id
        } catch {
            Write-Log "Unable to parse model ingestion response: $($_.Exception.Message)"
        }
    }
    if (-not $modelId) {
        $modelId = ($ModelURL.Split("/") | Where-Object { $_ } | Select-Object -Last 1)
        Write-Log "Fallback to model id derived from URL: $modelId"
    } else {
        Write-Log "Model id: $modelId"
    }

    # STEP 7: Authenticated GET /artifact/model/{id}
    Write-Log "Authenticated GET /artifact/model/$modelId"
    Invoke-LoggedRequest -Method GET -Uri "$API/artifact/model/$modelId" -Headers $headers

    # STEP 8: Dataset and code ingestion
    Write-Log "Ingesting dataset artifact"
    $datasetBody = '{"url":"https://huggingface.co/datasets/bookcorpus"}'
    Invoke-LoggedRequest -Method POST -Uri "$API/artifact/dataset" -Headers $headers -Body $datasetBody
    Invoke-LoggedRequest -Method GET -Uri "$API/artifact/dataset/bookcorpus" -Headers $headers

    Write-Log "Ingesting code artifact"
    $codeBody = '{"url":"https://github.com/openai/whisper"}'
    Invoke-LoggedRequest -Method POST -Uri "$API/artifact/code" -Headers $headers -Body $codeBody
    Invoke-LoggedRequest -Method GET -Uri "$API/artifact/code/whisper" -Headers $headers

    # STEP 9: Additional model uploads and listing
    Write-Log "Uploading additional models"
    $additionalModels = @(
        "https://huggingface.co/google-bert/bert-base-uncased",
        "https://huggingface.co/caidas/swin2SR-lightweight-x2-64",
        "https://huggingface.co/lerobot/diffusion_pusht"
    )
    foreach ($u in $additionalModels) {
        $body = @{ url = $u } | ConvertTo-Json -Compress
        Invoke-LoggedRequest -Method POST -Uri "$API/artifact/model" -Headers $headers -Body $body
    }

    Write-Log "Listing artifacts via POST /artifacts"
    $listBody = @(@{ name = "*" }) | ConvertTo-Json -Compress
    Invoke-LoggedRequest -Method POST -Uri "$API/artifacts" -Headers $headers -Body $listBody

    # STEP 10: Health and tracks endpoints without auth
    Write-Log "GET /health (no auth expected 200)"
    Invoke-LoggedRequest -Method GET -Uri "$API/health"

    Write-Log "GET /tracks (first call)"
    Invoke-LoggedRequest -Method GET -Uri "$API/tracks"

    Write-Log "GET /tracks (second call)"
    Invoke-LoggedRequest -Method GET -Uri "$API/tracks"

    # STEP 11: Registry reset with auth
    Write-Log "DELETE /reset (authenticated)"
    Invoke-LoggedRequest -Method DELETE -Uri "$API/reset" -Headers $headers

    Write-Log "Autograder replication sequence completed."
} finally {
    Stop-Transcript | Out-Null
}

# ============================
# === Strict Spec Validation ===
# ============================

# ---- tiny helpers (unique names to avoid collisions) ----
function _ParseJson2($content) {
    try { return $content | ConvertFrom-Json -ErrorAction Stop } catch { return $null }
  }
  function _Pass2([string]$m) { Write-Log "✅ $m" }
  function _Fail2([string]$m) { Write-Log "❌ $m" }
  function _AssertStatus2($resp, [int]$expect, [string]$label) {
    if ($resp -and [int]$resp.StatusCode -eq $expect) { _Pass2 "$label (status $expect)" }
    else { _Fail2 "$label (expected $expect, got $($resp?.StatusCode))" }
  }
  function _AssertExactError2($resp, [int]$code, [string]$detail) {
    $ok = $false
    if ($resp -and [int]$resp.StatusCode -eq $code) {
      $j = _ParseJson2 $resp.Content
      if ($j -and $j.detail -eq $detail) { $ok = $true }
    }
    if ($ok) { _Pass2 "Exact error ($code): '$detail'" } else { _Fail2 "Exact error mismatch. Wanted ($code): '$detail'." }
  }
  function _AssertIsArray2($json, [string]$label) {
    if ($null -ne $json -and ($json -is [System.Collections.IEnumerable]) -and -not ($json -is [string])) {
      _Pass2 "$label is array"
    } else {
      _Fail2 "$label is not array"
    }
  }
  function _AssertTriplet2($item, [string]$label) {
    $ok = $true
    if (-not $item.PSObject.Properties.Name -contains "name") { $ok = $false }
    if (-not $item.PSObject.Properties.Name -contains "id")   { $ok = $false }
    if (-not $item.PSObject.Properties.Name -contains "type") { $ok = $false }
    if ($ok) { _Pass2 "$label has {name,id,type}" } else { _Fail2 "$label missing required fields" }
  }
  function _AssertIdNumeric2($item, [string]$label) {
    $ok = $false
    if ($item.id -is [int] -or $item.id -is [long] -or ($item.id -as [long] -ne $null)) { $ok = $true }
    if ($ok) { _Pass2 "$label id is numeric" } else { _Fail2 "$label id is not numeric (got: $($item.id.GetType().Name): $($item.id))" }
  }
  function _AssertHasDownloadUrl2($obj, [string]$label) {
    if ($obj.data -and $obj.data.PSObject.Properties.Name -contains "download_url") {
      _Pass2 "$label includes data.download_url"
    } else {
      _Fail2 "$label missing data.download_url"
    }
  }
  
  Write-Log "=== Starting strict spec validation add-on ==="
  
  # Ensure we have a token and $headers; if not, authenticate now
  if (-not $headers) {
    if (-not (Test-Path $AuthFile)) { throw "Missing $AuthFile for strict checks." }
    $authBody2 = Get-Content -Raw -Path $AuthFile
    $authResp2 = Invoke-LoggedRequest -Method PUT -Uri "$API/authenticate" -Body $authBody2
    _AssertStatus2 $authResp2 200 "PUT /authenticate (strict)"
    $token2 = $authResp2.Content.Trim()
    $headers = @{
      "Content-Type"    = "application/json"
      "X-Authorization" = $token2
    }
  }
  
  # 1) Unauthenticated probes must have exact error strings
  $r = Invoke-LoggedRequest -Method GET -Uri "$API/artifact/byName/google-bert/bert-base-uncased"
  _AssertExactError2 $r 403 "Authentication failed due to invalid or missing AuthenticationToken"
  
  $r = Invoke-LoggedRequest -Method GET -Uri "$API/artifact/model/`$id"
  _AssertExactError2 $r 403 "Authentication failed due to invalid or missing AuthenticationToken"
  
  # GET /authenticate behavior (local 405 vs remote 500) — accept either
  $r = Invoke-LoggedRequest -Method GET -Uri "$API/authenticate"
  if ($API -eq $LocalAPI) { _AssertStatus2 $r 405 "GET /authenticate not allowed (local)" }
  else { _AssertStatus2 $r 500 "GET /authenticate remote 500" }
  
  # 2) Header discipline: Authorization should NOT be accepted; only X-Authorization
  $badHeaders2 = @{
    "Content-Type"  = "application/json"
    "Authorization" = $headers["X-Authorization"]
  }
  $r = Invoke-LoggedRequest -Method GET -Uri "$API/artifact/byName/google-bert/bert-base-uncased" -Headers $badHeaders2
  _AssertExactError2 $r 403 "Authentication failed due to invalid or missing AuthenticationToken"
  
  # 3) byName with auth => array of triplets with NUMERIC id
  $r = Invoke-LoggedRequest -Method GET -Uri "$API/artifact/byName/google-bert/bert-base-uncased" -Headers $headers
  if ($r.StatusCode -eq 200) {
    $arr = _ParseJson2 $r.Content
    _AssertIsArray2 $arr "/artifact/byName"
    if ($arr -and $arr.Count -gt 0) {
      _AssertTriplet2 $arr[0] "/artifact/byName[0]"
      _AssertIdNumeric2 $arr[0] "/artifact/byName[0]"
    }
  } else { _AssertStatus2 $r 200 "/artifact/byName" }
  
  # 4) Create model => example shows data.download_url; enforce it
  if (-not $ModelURL) {
    $ModelURL = "https://huggingface.co/google-bert/bert-base-uncased"
  }
  $body2 = @{ url = $ModelURL } | ConvertTo-Json -Compress
  $r = Invoke-LoggedRequest -Method POST -Uri "$API/artifact/model" -Headers $headers -Body $body2
  if ($r.StatusCode -in 201,409) {
    if ($r.StatusCode -eq 201) {
      $created2 = _ParseJson2 $r.Content
      if ($created2) { _AssertHasDownloadUrl2 $created2 "POST /artifact/model" }
    } else {
      _Pass2 "POST /artifact/model conflict acceptable (already exists)"
    }
  } else { _AssertStatus2 $r 201 "POST /artifact/model" }
  
  # 5) /artifacts must accept ARRAY body and return ARRAY of triplets; header "offset" must be STRING
  $listBody2 = @(@{ name = "*" }) | ConvertTo-Json -Compress
  $r = Invoke-LoggedRequest -Method POST -Uri "$API/artifacts" -Headers $headers -Body $listBody2
  _AssertStatus2 $r 200 "POST /artifacts"
  $arr2 = _ParseJson2 $r.Content
  _AssertIsArray2 $arr2 "POST /artifacts response"
  if ($arr2 -and $arr2.Count -gt 0) {
    _AssertTriplet2 $arr2[0] "/artifacts[0]"
    _AssertIdNumeric2 $arr2[0] "/artifacts[0]"
  }
  $offsetHeader2 = $r.Headers["offset"]
  if ($null -ne $offsetHeader2 -and ($offsetHeader2 -is [string])) { _Pass2 "offset header is string" } else { _Fail2 "offset header missing or not string" }
  
  # 6) /artifact/byRegEx must accept object body and return array of triplets (or 404 if no match)
  $regexBody2 = @{ regex = "bert" } | ConvertTo-Json -Compress
  $r = Invoke-LoggedRequest -Method POST -Uri "$API/artifact/byRegEx" -Headers $headers -Body $regexBody2
  if ($r.StatusCode -eq 200) {
    $arr3 = _ParseJson2 $r.Content
    _AssertIsArray2 $arr3 "/artifact/byRegEx response"
    if ($arr3 -and $arr3.Count -gt 0) {
      _AssertTriplet2 $arr3[0] "/artifact/byRegEx[0]"
      _AssertIdNumeric2 $arr3[0] "/artifact/byRegEx[0]"
    }
  } elseif ($r.StatusCode -eq 404) {
    _Pass2 "/artifact/byRegEx 404 acceptable if no matches"
  } else {
    _AssertStatus2 $r 200 "/artifact/byRegEx"
  }
  
  Write-Log "=== Strict spec validation add-on complete ==="
  