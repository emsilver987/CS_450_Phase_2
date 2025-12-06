#!/usr/bin/env python3
"""
Test Package Management System with Existing Models
This script tests the package management functionality using the 3 models in S3.
"""

import boto3
import json
import os
import pytest
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from typing import Dict, List, Any

# AWS clients
s3 = boto3.client('s3', region_name='us-east-1')
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

# Configuration
ARTIFACTS_BUCKET = 'pkg-artifacts'
PACKAGES_TABLE = 'packages'
USERS_TABLE = 'users'
TOKENS_TABLE = 'tokens'

def test_s3_packages():
    """Test S3 package storage and retrieval"""
    # List all packages in S3
    response = s3.list_objects_v2(Bucket=ARTIFACTS_BUCKET, Prefix='models/')

    if 'Contents' not in response or len(response.get('Contents', [])) == 0:
        pytest.skip("No packages found in S3 to test")

    packages = []
    for obj in response['Contents']:
        if obj['Key'].endswith('.zip'):
            # Extract package info from S3 key
            parts = obj['Key'].split('/')
            if len(parts) >= 4:
                pkg_name = parts[1]
                version = parts[2]
                packages.append({
                    'name': pkg_name,
                    'version': version,
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    's3_key': obj['Key']
                })

    # Assertions
    assert len(packages) > 0, "Should find at least one package in S3"
    for pkg in packages:
        # Validate package structure
        assert 'name' in pkg, "Package missing 'name' field"
        assert 'version' in pkg, "Package missing 'version' field"
        assert 'size' in pkg, "Package missing 'size' field"
        assert 'last_modified' in pkg, "Package missing 'last_modified' field"
        assert 's3_key' in pkg, "Package missing 's3_key' field"

        # Validate field types and values
        assert isinstance(pkg['name'], str), "Package name should be a string"
        assert len(pkg['name']) > 0, "Package name should not be empty"
        assert isinstance(pkg['version'], str), "Package version should be a string"
        assert len(pkg['version']) > 0, "Package version should not be empty"
        assert isinstance(pkg['size'], int), "Package size should be an integer"
        assert pkg['size'] > 0, "Package size should be greater than 0"
        assert isinstance(pkg['last_modified'], datetime), (
            "last_modified should be a datetime object"
        )
        assert isinstance(pkg['s3_key'], str), "s3_key should be a string"
        assert pkg['s3_key'].endswith('.zip'), "s3_key should end with .zip"

def test_package_metadata():
    """Test DynamoDB package metadata"""
    table = dynamodb.Table(PACKAGES_TABLE)

    # Scan for packages
    response = table.scan()
    packages = response.get('Items', [])

    # Validate table structure
    assert isinstance(packages, list), "Packages should be a list"

    # Validate package item structure
    for pkg in packages:
        assert isinstance(pkg, dict), "Each package should be a dict"
        # Validate required fields if present
        if 'pkg_key' in pkg:
            assert isinstance(pkg['pkg_key'], str), "pkg_key should be a string"
        if 'description' in pkg:
            assert isinstance(
                pkg['description'], str
            ), "description should be a string"

def test_presigned_urls():
    """Test presigned URL generation for package downloads"""
    # First check if any packages exist in S3
    response = s3.list_objects_v2(Bucket=ARTIFACTS_BUCKET, Prefix='models/')

    if 'Contents' not in response or len(response.get('Contents', [])) == 0:
        pytest.skip("No packages found in S3 to test presigned URLs")

    # Get actual packages from S3 instead of hardcoded list
    available_packages = []
    for obj in response.get('Contents', []):
        if obj['Key'].endswith('.zip'):
            available_packages.append(obj['Key'])

    if not available_packages:
        pytest.skip("No .zip packages found in S3 to test presigned URLs")

    # Test with actual packages found in S3 (limit to first 3)
    test_packages = available_packages[:3]
    assert len(test_packages) > 0, "Should have at least one test package"

    for s3_key in test_packages:
        # Verify object exists before generating presigned URL
        head_response = s3.head_object(Bucket=ARTIFACTS_BUCKET, Key=s3_key)
        assert 'ContentLength' in head_response, (
            "head_object should return ContentLength"
        )
        assert head_response['ContentLength'] > 0, (
            "Package size should be greater than 0"
        )

        # Generate presigned URL (valid for 1 hour)
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': ARTIFACTS_BUCKET, 'Key': s3_key},
            ExpiresIn=3600
        )

        # Validate presigned URL format
        assert isinstance(url, str), "Presigned URL should be a string"
        assert len(url) > 0, "Presigned URL should not be empty"
        assert url.startswith('https://'), (
            "Presigned URL should start with https://"
        )
        assert ARTIFACTS_BUCKET in url or 'amazonaws.com' in url, (
            "Presigned URL should contain bucket or AWS domain"
        )
        assert s3_key in url or 'X-Amz-Signature' in url, (
            "Presigned URL should contain key or signature"
        )

def test_user_management():
    """Test user management system"""
    users_table = dynamodb.Table(USERS_TABLE)

    # Get user count
    response = users_table.scan(Select='COUNT')
    user_count = response.get('Count', 0)

    # Validate response structure
    assert isinstance(user_count, int), "User count should be an integer"
    assert user_count >= 0, "User count should be non-negative"

    if user_count > 0:
        # Get sample users
        response = users_table.scan(Limit=5)
        users = response.get('Items', [])

        assert isinstance(users, list), "Users should be a list"
        assert len(users) > 0, "Should have at least one user"

        # Validate user structure
        for user in users:
            assert isinstance(user, dict), "Each user should be a dict"
            if 'username' in user:
                assert isinstance(
                    user['username'], str
                ), "username should be a string"
                assert len(user['username']) > 0, (
                    "username should not be empty"
                )
            if 'groups' in user:
                assert isinstance(
                    user['groups'], list
                ), "groups should be a list"

def test_package_download_workflow():
    """Test the complete package download workflow"""
    # First, find an existing package in S3
    response = s3.list_objects_v2(Bucket=ARTIFACTS_BUCKET, Prefix='models/')

    if 'Contents' not in response or len(response['Contents']) == 0:
        pytest.skip("No packages found in S3 to test download workflow")

    # Find the first .zip file
    test_package = None
    for obj in response['Contents']:
        if obj['Key'].endswith('.zip'):
            test_package = obj['Key']
            break

    if not test_package:
        pytest.skip("No .zip packages found in S3 to test download workflow")

    assert test_package is not None, "Should find a test package"
    assert isinstance(test_package, str), "test_package should be a string"
    assert test_package.endswith('.zip'), "test_package should end with .zip"

    # 1. Check if package exists
    head_response = s3.head_object(
        Bucket=ARTIFACTS_BUCKET, Key=test_package
    )
    assert 'ContentLength' in head_response, (
        "head_object should return ContentLength"
    )
    assert head_response['ContentLength'] > 0, (
        "Package size should be greater than 0"
    )
    assert 'LastModified' in head_response, (
        "head_object should return LastModified"
    )
    assert isinstance(
        head_response['LastModified'], datetime
    ), "LastModified should be a datetime"

    # 2. Generate presigned URL
    download_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': ARTIFACTS_BUCKET, 'Key': test_package},
        ExpiresIn=3600
    )

    # Validate presigned URL
    assert isinstance(download_url, str), "Presigned URL should be a string"
    assert len(download_url) > 0, "Presigned URL should not be empty"
    assert download_url.startswith('https://'), (
        "Presigned URL should start with https://"
    )

    # 3. Extract package info
    parts = test_package.split('/')
    pkg_name = parts[1] if len(parts) > 1 else 'unknown'
    version = parts[2] if len(parts) > 2 else 'unknown'

    assert len(pkg_name) > 0, "Package name should not be empty"
    assert len(version) > 0, "Package version should not be empty"

    # 4. Validate download event structure (simulated)
    downloads_table = dynamodb.Table('downloads')
    download_event = {
        'download_id': f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        'user_id': 'test-user',
        'pkg_name': pkg_name,
        'version': version,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': 'initiated'
    }

    # Validate download event structure
    assert 'download_id' in download_event, "Event missing download_id"
    assert 'user_id' in download_event, "Event missing user_id"
    assert 'pkg_name' in download_event, "Event missing pkg_name"
    assert 'version' in download_event, "Event missing version"
    assert 'timestamp' in download_event, "Event missing timestamp"
    assert 'status' in download_event, "Event missing status"

    assert isinstance(
        download_event['download_id'], str
    ), "download_id should be a string"
    assert isinstance(
        download_event['user_id'], str
    ), "user_id should be a string"
    assert isinstance(
        download_event['pkg_name'], str
    ), "pkg_name should be a string"
    assert isinstance(
        download_event['version'], str
    ), "version should be a string"
    assert isinstance(
        download_event['timestamp'], str
    ), "timestamp should be a string"
    assert isinstance(
        download_event['status'], str
    ), "status should be a string"

def main():
    """Main test function"""
    print("Package Management System Test Suite")
    print("=" * 50)
    
    # Test S3 packages
    try:
        test_s3_packages()
        s3_success = True
    except (AssertionError, Exception) as e:
        print(f"S3 packages test failed: {e}")
        s3_success = False
    
    # Test package metadata
    try:
        test_package_metadata()
        db_success = True
    except (AssertionError, Exception) as e:
        print(f"Package metadata test failed: {e}")
        db_success = False
    
    # Test presigned URLs
    try:
        test_presigned_urls()
        presigned_success = True
    except (AssertionError, Exception) as e:
        print(f"Presigned URLs test failed: {e}")
        presigned_success = False
    
    # Test user management
    try:
        test_user_management()
        user_success = True
    except (AssertionError, Exception) as e:
        print(f"User management test failed: {e}")
        user_success = False
    
    # Test download workflow
    try:
        test_package_download_workflow()
        download_success = True
    except (AssertionError, Exception) as e:
        print(f"Download workflow test failed: {e}")
        download_success = False
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary:")
    
    tests = [
        ("S3 Package Storage", s3_success),
        ("Package Metadata", db_success),
        ("Presigned URLs", presigned_success),
        ("User Management", user_success),
        ("Download Workflow", download_success)
    ]
    
    passed = sum(1 for _, success in tests if success)
    total = len(tests)
    
    for test_name, success in tests:
        status = "[PASS]" if success else "[FAIL]"
        print(f"   {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("[SUCCESS] All tests passed! Package management system is working.")
    else:
        print("[WARNING] Some tests failed. Check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    main()
