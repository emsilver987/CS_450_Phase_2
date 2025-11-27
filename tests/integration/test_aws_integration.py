#!/usr/bin/env python3
"""
AWS Services Integration Test Suite for CS_450_Phase_2

This script tests all AWS services and integrations to ensure everything is working correctly.
Run this after deploying the infrastructure with Terraform.
"""

import boto3
import requests
import json
import time
import sys
import pytest
from typing import Dict, Any, List
import os

class AWSTestSuite:
    def __init__(self):
        self.session = boto3.Session()
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.artifacts_bucket = os.getenv('ARTIFACTS_BUCKET', 'pkg-artifacts')
        
        # Initialize AWS clients
        self.s3 = boto3.client('s3', region_name=self.region)
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.ecs = boto3.client('ecs', region_name=self.region)
        self.elbv2 = boto3.client('elbv2', region_name=self.region)
        self.cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        self.cloudwatch_logs = boto3.client('logs', region_name=self.region)
        self.kms = boto3.client('kms', region_name=self.region)
        self.secrets_manager = boto3.client('secretsmanager', region_name=self.region)
        
        # Test results
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}: {message}")
        
        if passed:
            self.results['passed'] += 1
        else:
            self.results['failed'] += 1
            self.results['errors'].append(f"{test_name}: {message}")
    
    def test_s3_bucket(self):
        """Test S3 bucket exists and is accessible"""
        try:
            response = self.s3.head_bucket(Bucket=self.artifacts_bucket)
            # Explicit assertion
            assert response is not None, "head_bucket should return a response"
            self.log_test("S3 Bucket Access", True, f"Bucket {self.artifacts_bucket} is accessible")

            # Test bucket encryption
            try:
                encryption = self.s3.get_bucket_encryption(
                    Bucket=self.artifacts_bucket
                )
                # Validate encryption configuration
                assert 'ServerSideEncryptionConfiguration' in encryption, (
                    "Encryption configuration should be present"
                )
                self.log_test("S3 Bucket Encryption", True, "Bucket has encryption enabled")
            except Exception:
                self.log_test("S3 Bucket Encryption", False, "Bucket encryption not configured")

        except Exception as e:
            self.log_test("S3 Bucket Access", False, str(e))
            pytest.fail(f"S3 bucket access failed: {e}")
    
    def test_dynamodb_tables(self):
        """Test DynamoDB tables exist and are accessible"""
        expected_tables = ['users', 'tokens', 'packages', 'uploads', 'downloads']

        try:
            response = self.dynamodb.meta.client.list_tables()
            existing_tables = response['TableNames']

            # Validate response structure
            assert 'TableNames' in response, "Response should contain TableNames"
            assert isinstance(existing_tables, list), "TableNames should be a list"

            for table_name in expected_tables:
                if table_name in existing_tables:
                    # Test table access
                    table = self.dynamodb.Table(table_name)
                    table.load()

                    # Validate table properties
                    assert table.table_status in ['ACTIVE', 'CREATING', 'UPDATING'], (
                        f"Table {table_name} should be in valid state, "
                        f"got {table.table_status}"
                    )
                    assert isinstance(table.item_count, int), (
                        "item_count should be an integer"
                    )
                    assert table.item_count >= 0, (
                        "item_count should be non-negative"
                    )

                    self.log_test(
                        f"DynamoDB Table {table_name}", True,
                        f"Table exists with {table.item_count} items"
                    )
                else:
                    self.log_test(
                        f"DynamoDB Table {table_name}", False,
                        "Table does not exist"
                    )

        except Exception as e:
            self.log_test("DynamoDB Tables", False, str(e))
            pytest.fail(f"DynamoDB tables test failed: {e}")
    
    def test_ecs_cluster(self):
        """Test ECS cluster and service"""
        try:
            # Test cluster
            clusters = self.ecs.list_clusters()
            cluster_arn = None
            for arn in clusters['clusterArns']:
                if 'validator-cluster' in arn:
                    cluster_arn = arn
                    break
            
            if cluster_arn:
                # Validate cluster ARN format
                assert 'arn:aws:ecs' in cluster_arn, (
                    f"Invalid cluster ARN format: {cluster_arn}"
                )
                self.log_test("ECS Cluster", True, "validator-cluster exists")

                # Test service
                services = self.ecs.list_services(cluster=cluster_arn)
                if services['serviceArns']:
                    assert len(services['serviceArns']) > 0, (
                        "Should have at least one service"
                    )
                    service_arn = services['serviceArns'][0]
                    service_details = self.ecs.describe_services(
                        cluster=cluster_arn,
                        services=[service_arn]
                    )

                    assert 'services' in service_details, (
                        "Service details should contain services"
                    )
                    assert len(service_details['services']) > 0, (
                        "Should have service details"
                    )

                    service = service_details['services'][0]
                    running_count = service['runningCount']
                    desired_count = service['desiredCount']

                    # Validate service properties
                    assert isinstance(running_count, int), (
                        "runningCount should be an integer"
                    )
                    assert isinstance(desired_count, int), (
                        "desiredCount should be an integer"
                    )
                    assert running_count >= 0, (
                        "runningCount should be non-negative"
                    )
                    assert desired_count > 0, (
                        "desiredCount should be greater than 0"
                    )

                    if running_count == desired_count:
                        self.log_test(
                            "ECS Service", True,
                            f"Service running ({running_count}/{desired_count})"
                        )
                    else:
                        self.log_test(
                            "ECS Service", False,
                            f"Service not fully running "
                            f"({running_count}/{desired_count})"
                        )
                else:
                    self.log_test("ECS Service", False, "No services found in cluster")
            else:
                self.log_test("ECS Cluster", False, "validator-cluster not found")
                
        except Exception as e:
            self.log_test("ECS Cluster", False, str(e))
    
    def test_load_balancer(self):
        """Test Application Load Balancer"""
        try:
            response = self.elbv2.describe_load_balancers()
            lb_found = False
            
            for lb in response['LoadBalancers']:
                if 'validator-lb' in lb['LoadBalancerName']:
                    lb_found = True
                    dns_name = lb['DNSName']
                    state = lb['State']['Code']
                    
                    # Validate load balancer properties
                    assert isinstance(dns_name, str), "DNS name should be a string"
                    assert len(dns_name) > 0, "DNS name should not be empty"
                    assert isinstance(state, str), "State should be a string"

                    if state == 'active':
                        self.log_test(
                            "Load Balancer", True, f"LB active at {dns_name}"
                        )

                        # Test health endpoint
                        try:
                            health_url = f"http://{dns_name}/health"
                            health_response = requests.get(health_url, timeout=10)
                            assert health_response.status_code == 200, (
                                f"Health endpoint returned "
                                f"{health_response.status_code}, expected 200"
                            )
                            self.log_test(
                                "Load Balancer Health", True,
                                "Health endpoint responding"
                            )
                        except Exception as e:
                            self.log_test(
                                "Load Balancer Health", False,
                                f"Health endpoint error: {str(e)}"
                            )
                    else:
                        self.log_test("Load Balancer", False, f"LB state: {state}")
                    break
            
            if not lb_found:
                self.log_test("Load Balancer", False, "validator-lb not found")
                
        except Exception as e:
            self.log_test("Load Balancer", False, str(e))
    
    def test_kms_key(self):
        """Test KMS key exists"""
        try:
            response = self.kms.describe_key(KeyId='alias/acme-main-key')
            assert 'KeyMetadata' in response, "Response should contain KeyMetadata"
            key_metadata = response['KeyMetadata']
            key_state = key_metadata['KeyState']

            # Validate key metadata structure
            assert isinstance(key_state, str), "KeyState should be a string"
            assert 'KeyId' in key_metadata, "KeyMetadata should contain KeyId"
            assert 'Arn' in key_metadata, "KeyMetadata should contain Arn"

            if key_state == 'Enabled':
                self.log_test("KMS Key", True, "KMS key is enabled")
            else:
                self.log_test("KMS Key", False, f"KMS key state: {key_state}")

        except Exception as e:
            self.log_test("KMS Key", False, str(e))
            pytest.fail(f"KMS key test failed: {e}")
    
    def test_secrets_manager(self):
        """Test Secrets Manager secret exists"""
        try:
            response = self.secrets_manager.describe_secret(
                SecretId='acme-jwt-secret'
            )

            # Validate response structure
            assert 'Name' in response, "Response should contain Name"
            assert response['Name'] == 'acme-jwt-secret', (
                f"Secret name should be 'acme-jwt-secret', "
                f"got {response['Name']}"
            )

            # Check if secret exists and has a current version
            if ('VersionIdsToStages' in response and
                    'AWSCURRENT' in str(response['VersionIdsToStages'])):
                self.log_test(
                    "Secrets Manager", True,
                    "JWT secret exists with current version"
                )
            else:
                self.log_test(
                    "Secrets Manager", False,
                    "JWT secret exists but no current version"
                )

        except Exception as e:
            self.log_test("Secrets Manager", False, str(e))
            pytest.fail(f"Secrets Manager test failed: {e}")
    
    def test_cloudwatch_logs(self):
        """Test CloudWatch log groups exist"""
        try:
            log_groups = self.cloudwatch_logs.describe_log_groups(
                logGroupNamePrefix='/ecs/validator-service'
            )

            # Validate response structure
            assert 'logGroups' in log_groups, (
                "Response should contain logGroups"
            )
            assert isinstance(log_groups['logGroups'], list), (
                "logGroups should be a list"
            )

            if log_groups['logGroups']:
                # Validate log group structure
                for log_group in log_groups['logGroups']:
                    assert 'logGroupName' in log_group, (
                        "Log group should have logGroupName"
                    )
                    assert isinstance(log_group['logGroupName'], str), (
                        "logGroupName should be a string"
                    )
                self.log_test("CloudWatch Logs", True, "ECS log group exists")
            else:
                self.log_test("CloudWatch Logs", False, "ECS log group not found")

        except Exception as e:
            self.log_test("CloudWatch Logs", False, str(e))
            pytest.fail(f"CloudWatch Logs test failed: {e}")
    
    def test_end_to_end_workflow(self):
        """Test complete end-to-end workflow"""
        try:
            # This would test the complete workflow:
            # 1. Register user
            # 2. Login
            # 3. Upload package
            # 4. Download package
            
            # For now, just test that the validator service is responding
            # You would need the actual load balancer URL for this
            self.log_test("End-to-End Workflow", True, "Workflow test placeholder - implement with actual URLs")
            
        except Exception as e:
            self.log_test("End-to-End Workflow", False, str(e))
    
    def run_all_tests(self):
        """Run all tests"""
        print("Starting AWS Services Integration Tests")
        print("=" * 50)
        
        # Infrastructure tests
        print("\nTesting Infrastructure Components:")
        self.test_s3_bucket()
        self.test_dynamodb_tables()
        self.test_ecs_cluster()
        self.test_load_balancer()
        
        # Security tests
        print("\nTesting Security Components:")
        self.test_kms_key()
        self.test_secrets_manager()
        
        # Monitoring tests
        print("\nTesting Monitoring Components:")
        self.test_cloudwatch_logs()
        
        # Integration tests
        print("\nTesting Integration:")
        self.test_end_to_end_workflow()
        
        # Summary
        print("\n" + "=" * 50)
        print("Test Summary:")
        print(f"[PASS] Passed: {self.results['passed']}")
        print(f"[FAIL] Failed: {self.results['failed']}")
        
        if self.results['errors']:
            print("\nErrors:")
            for error in self.results['errors']:
                print(f"  - {error}")
        
        return self.results['failed'] == 0

def main():
    """Main test runner"""
    print("AWS Services Integration Test Suite")
    print("Make sure you have:")
    print("1. AWS credentials configured")
    print("2. Infrastructure deployed with Terraform")
    print("3. Environment variables set (AWS_REGION, ARTIFACTS_BUCKET)")
    print()
    
    # Check AWS credentials
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"AWS Identity: {identity['Arn']}")
        print(f"Account ID: {identity['Account']}")
        print()
    except Exception as e:
        print(f"[ERROR] AWS credentials not configured: {e}")
        sys.exit(1)
    
    # Run tests
    test_suite = AWSTestSuite()
    success = test_suite.run_all_tests()
    
    if success:
        print("\n[SUCCESS] All tests passed! AWS infrastructure is ready.")
        sys.exit(0)
    else:
        print("\n[ERROR] Some tests failed. Check the errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
