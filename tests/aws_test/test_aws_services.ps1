# Comprehensive AWS Services Test Script
# Tests all AWS services used by the API

Write-Host "=== Testing AWS Services Connection ===" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:AWS_REGION = "us-east-1"
$env:AWS_ACCOUNT_ID = "838693051036"
$env:S3_ACCESS_POINT_NAME = "cs450-s3"

Write-Host "Environment Variables Set:" -ForegroundColor Yellow
Write-Host "  AWS_REGION = $env:AWS_REGION" -ForegroundColor Gray
Write-Host "  AWS_ACCOUNT_ID = $env:AWS_ACCOUNT_ID" -ForegroundColor Gray
Write-Host "  S3_ACCESS_POINT_NAME = $env:S3_ACCESS_POINT_NAME" -ForegroundColor Gray
Write-Host ""

# Test 1: AWS Credentials
Write-Host "1. Testing AWS Credentials (STS)..." -ForegroundColor Yellow
try {
    $identity = aws sts get-caller-identity --region us-east-1 2>&1
    if ($LASTEXITCODE -eq 0) {
        $identityObj = $identity | ConvertFrom-Json
        Write-Host "   [OK] AWS Credentials valid" -ForegroundColor Green
        Write-Host "        Account: $($identityObj.Account)" -ForegroundColor Gray
        Write-Host "        User: $($identityObj.Arn)" -ForegroundColor Gray
    } else {
        Write-Host "   [FAIL] AWS Credentials invalid" -ForegroundColor Red
        Write-Host "        Error: $identity" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "   [FAIL] Error checking credentials: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test 2: S3 Access Point
Write-Host "2. Testing S3 Access Point..." -ForegroundColor Yellow
$apArn = "arn:aws:s3:us-east-1:838693051036:accesspoint/cs450-s3"
try {
    $result = aws s3api list-objects-v2 --bucket $apArn --prefix "models/" --max-items 1 --region us-east-1 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   [OK] S3 Access Point accessible" -ForegroundColor Green
        Write-Host "        ARN: $apArn" -ForegroundColor Gray
    } else {
        Write-Host "   [WARN] S3 Access Point test returned: $result" -ForegroundColor Yellow
        Write-Host "        This may still work - checking with Python..." -ForegroundColor Gray
    }
} catch {
    Write-Host "   [WARN] Could not test S3 via CLI: $_" -ForegroundColor Yellow
}
Write-Host ""

# Test 3: DynamoDB Tables
Write-Host "3. Testing DynamoDB Tables..." -ForegroundColor Yellow
$tables = @("users", "tokens", "packages", "uploads", "downloads")
$region = "us-east-1"

foreach ($table in $tables) {
    try {
        $tableInfo = aws dynamodb describe-table --table-name $table --region $region 2>&1
        if ($LASTEXITCODE -eq 0) {
            $tableObj = $tableInfo | ConvertFrom-Json
            $status = $tableObj.Table.TableStatus
            $itemCount = $tableObj.Table.ItemCount
            if ($status -eq "ACTIVE") {
                Write-Host "   [OK] Table '$table' - Status: $status, Items: $itemCount" -ForegroundColor Green
            } else {
                Write-Host "   [WARN] Table '$table' - Status: $status" -ForegroundColor Yellow
            }
        } else {
            Write-Host "   [FAIL] Table '$table' - Not found or inaccessible" -ForegroundColor Red
            Write-Host "        Error: $tableInfo" -ForegroundColor Red
        }
    } catch {
        Write-Host "   [FAIL] Table '$table' - Error: $_" -ForegroundColor Red
    }
}
Write-Host ""

# Test 4: Python Module Test
Write-Host "4. Testing Python AWS Module Connection..." -ForegroundColor Yellow
try {
    $pythonTest = python -c @"
import os
import sys
sys.path.insert(0, 'src')

# Set environment variables
os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_ACCOUNT_ID'] = '838693051036'
os.environ['S3_ACCESS_POINT_NAME'] = 'cs450-s3'

# Test s3_service
from src.services import s3_service
print(f'S3 Service - aws_available: {s3_service.aws_available}')
print(f'S3 Service - s3 client: {s3_service.s3 is not None}')
print(f'S3 Service - ap_arn: {s3_service.ap_arn}')

# Test auth_service DynamoDB
from src.services import auth_service
try:
    table = auth_service.dynamodb.Table('users')
    table.load()
    print(f'DynamoDB - users table: {table.table_status}')
except Exception as e:
    print(f'DynamoDB - users table error: {e}')

# Test package_service
from src.services import package_service
try:
    table = package_service.dynamodb.Table('packages')
    table.load()
    print(f'DynamoDB - packages table: {table.table_status}')
except Exception as e:
    print(f'DynamoDB - packages table error: {e}')
"@
    
    Write-Host "   Python Module Results:" -ForegroundColor Cyan
    $pythonTest | ForEach-Object {
        if ($_ -match "aws_available: True" -or $_ -match "table_status: ACTIVE") {
            Write-Host "   [OK] $_" -ForegroundColor Green
        } elseif ($_ -match "aws_available: False" -or $_ -match "error:") {
            Write-Host "   [FAIL] $_" -ForegroundColor Red
        } else {
            Write-Host "   $_" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "   [FAIL] Python test error: $_" -ForegroundColor Red
}
Write-Host ""

# Test 5: Test Upload Function Directly
Write-Host "5. Testing upload_model function directly..." -ForegroundColor Yellow
try {
    $uploadTest = python -c @"
import os
import sys
sys.path.insert(0, 'src')

os.environ['AWS_REGION'] = 'us-east-1'
os.environ['AWS_ACCOUNT_ID'] = '838693051036'
os.environ['S3_ACCESS_POINT_NAME'] = 'cs450-s3'

from src.services import s3_service

if s3_service.aws_available:
    print('aws_available: True')
    try:
        # Test with minimal content (should fail with empty content error, not 503)
        result = s3_service.upload_model(b'test', 'test-model', '1.0.0')
        print('Upload test: SUCCESS')
    except Exception as e:
        if '503' in str(e) or 'not available' in str(e).lower():
            print(f'Upload test: FAILED - {e}')
        else:
            print(f'Upload test: Expected error (not 503): {e}')
else:
    print('aws_available: False')
    print('Upload test: FAILED - AWS not available')
"@
    
    Write-Host "   Upload Function Test:" -ForegroundColor Cyan
    $uploadTest | ForEach-Object {
        if ($_ -match "aws_available: True" -or $_ -match "SUCCESS" -or $_ -match "Expected error") {
            Write-Host "   [OK] $_" -ForegroundColor Green
        } elseif ($_ -match "FAILED" -or $_ -match "aws_available: False") {
            Write-Host "   [FAIL] $_" -ForegroundColor Red
        } else {
            Write-Host "   $_" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "   [FAIL] Upload test error: $_" -ForegroundColor Red
}
Write-Host ""

# Summary
Write-Host "=== Test Summary ===" -ForegroundColor Cyan
Write-Host "If all tests pass, AWS services are properly configured." -ForegroundColor White
Write-Host "If upload_model fails, check the server logs for debug output." -ForegroundColor Yellow
Write-Host ""


