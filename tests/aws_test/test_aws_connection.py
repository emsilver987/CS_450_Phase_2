#!/usr/bin/env python3
"""Test AWS connection and aws_available variable"""

import os
import sys

# Set environment variables if not set
if not os.getenv("AWS_REGION"):
    os.environ["AWS_REGION"] = "us-east-1"
if not os.getenv("AWS_ACCOUNT_ID"):
    os.environ["AWS_ACCOUNT_ID"] = "838693051036"
if not os.getenv("S3_ACCESS_POINT_NAME"):
    os.environ["S3_ACCESS_POINT_NAME"] = "cs450-s3"

print("Environment Variables:")
print(f"  AWS_REGION: {os.getenv('AWS_REGION')}")
print(f"  AWS_ACCOUNT_ID: {os.getenv('AWS_ACCOUNT_ID')}")
print(f"  S3_ACCESS_POINT_NAME: {os.getenv('S3_ACCESS_POINT_NAME')}")
print()

# Import the s3_service module to check aws_available
sys.path.insert(0, "src")
from src.services import s3_service

print(f"AWS Available: {s3_service.aws_available}")
print(f"S3 Client: {s3_service.s3 is not None}")
print(f"AP ARN: {s3_service.ap_arn}")
print()

if s3_service.aws_available:
    print("[OK] AWS services are available")
    try:
        # Test upload_model function availability
        result = s3_service.upload_model(b"test", "test-model", "1.0.0")
        print("❌ Upload should have failed with empty content, but didn't")
    except Exception as e:
        if "empty file" in str(e).lower() or "400" in str(e):
            print("[OK] upload_model function is working (correctly rejected empty content)")
        else:
            print(f"[WARN] Unexpected error: {e}")
else:
    print("[ERROR] AWS services are NOT available")
    print("This is why uploads are failing!")

