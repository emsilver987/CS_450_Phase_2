# PowerShell script to check logs for performance endpoint issues

$Region = "us-east-1"
$EcsLogGroup = "/ecs/validator-service"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Performance Endpoint Log Diagnostics" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check ECS logs for [PERF] messages
Write-Host "1. Checking ECS logs for [PERF] messages..." -ForegroundColor Yellow
Write-Host "-------------------------------------------" -ForegroundColor Gray
try {
    $perfLogs = aws logs filter-log-events `
        --log-group-name $EcsLogGroup `
        --filter-pattern "[PERF]" `
        --region $Region `
        --max-items 50 `
        --query 'events[*].[timestamp,message]' `
        --output table 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $perfLogs
    } else {
        Write-Host "No [PERF] messages found or log group doesn't exist" -ForegroundColor Red
    }
} catch {
    Write-Host "Error checking [PERF] logs: $_" -ForegroundColor Red
}
Write-Host ""

# 2. Check for errors in ECS logs
Write-Host "2. Checking ECS logs for errors..." -ForegroundColor Yellow
Write-Host "-------------------------------------------" -ForegroundColor Gray
try {
    $errorLogs = aws logs filter-log-events `
        --log-group-name $EcsLogGroup `
        --filter-pattern "ERROR" `
        --region $Region `
        --max-items 20 `
        --query 'events[*].[timestamp,message]' `
        --output table 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $errorLogs
    } else {
        Write-Host "No errors found" -ForegroundColor Green
    }
} catch {
    Write-Host "Error checking error logs: $_" -ForegroundColor Red
}
Write-Host ""

# 3. Check for endpoint registration
Write-Host "3. Checking for endpoint registration messages..." -ForegroundColor Yellow
Write-Host "-------------------------------------------" -ForegroundColor Gray
try {
    $regLogs = aws logs filter-log-events `
        --log-group-name $EcsLogGroup `
        --filter-pattern "Performance download endpoint" `
        --region $Region `
        --max-items 10 `
        --query 'events[*].[timestamp,message]' `
        --output table 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host $regLogs
    } else {
        Write-Host "No registration messages found" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error checking registration logs: $_" -ForegroundColor Red
}
Write-Host ""

# 4. Get latest log stream
Write-Host "4. Latest log stream info..." -ForegroundColor Yellow
Write-Host "-------------------------------------------" -ForegroundColor Gray
try {
    $streams = aws logs describe-log-streams `
        --log-group-name $EcsLogGroup `
        --order-by LastEventTime `
        --descending `
        --max-items 1 `
        --region $Region `
        --query 'logStreams[0].logStreamName' `
        --output text 2>&1
    
    if ($streams -and $streams -ne "None") {
        Write-Host "Latest stream: $streams" -ForegroundColor Green
        Write-Host ""
        Write-Host "Last 20 log entries:" -ForegroundColor Cyan
        
        $events = aws logs get-log-events `
            --log-group-name $EcsLogGroup `
            --log-stream-name $streams `
            --limit 20 `
            --region $Region `
            --query 'events[*].message' `
            --output text 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $events -split "`n" | Select-Object -Last 20 | ForEach-Object { Write-Host $_ }
        }
    } else {
        Write-Host "No log streams found" -ForegroundColor Red
    }
} catch {
    Write-Host "Error getting latest stream: $_" -ForegroundColor Red
}
Write-Host ""

# 5. Get API Gateway ID
Write-Host "5. Getting API Gateway information..." -ForegroundColor Yellow
Write-Host "-------------------------------------------" -ForegroundColor Gray
try {
    $apiId = aws apigateway get-rest-apis `
        --region $Region `
        --query "items[?name=='main-api'].id" `
        --output text 2>&1
    
    if ($apiId -and $apiId -ne "None") {
        Write-Host "API Gateway ID: $apiId" -ForegroundColor Green
        $apiLogGroup = "/aws/apigateway/$apiId/prod"
        Write-Host "API Gateway Log Group: $apiLogGroup" -ForegroundColor Green
        Write-Host ""
        
        # Check if log group exists
        $logGroupCheck = aws logs describe-log-groups `
            --log-group-name-prefix $apiLogGroup `
            --region $Region `
            --query 'logGroups[0].logGroupName' `
            --output text 2>&1
        
        if ($logGroupCheck -like "*$apiLogGroup*") {
            Write-Host "Searching for performance endpoint requests..." -ForegroundColor Cyan
            $apiLogs = aws logs filter-log-events `
                --log-group-name $apiLogGroup `
                --filter-pattern "performance" `
                --region $Region `
                --max-items 20 `
                --query 'events[*].[timestamp,message]' `
                --output table 2>&1
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host $apiLogs
            } else {
                Write-Host "No performance endpoint requests found" -ForegroundColor Yellow
            }
        } else {
            Write-Host "API Gateway log group not found (logging may not be enabled)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Could not find API Gateway" -ForegroundColor Red
    }
} catch {
    Write-Host "Error getting API Gateway info: $_" -ForegroundColor Red
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Diagnostics Complete" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

