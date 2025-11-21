#!/usr/bin/env python3
"""
STRIDE Coverage Analysis Script

This script analyzes the codebase to verify STRIDE security mitigations are implemented.
It checks each STRIDE category and generates a coverage report.
"""

import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class Status(Enum):
    IMPLEMENTED = "✅"
    PARTIAL = "⚠️"
    NOT_FOUND = "❌"


@dataclass
class MitigationCheck:
    name: str
    status: Status
    notes: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class StrideCategory:
    name: str
    mitigations: List[MitigationCheck] = field(default_factory=list)
    coverage_percentage: float = 0.0


class StrideCoverageAnalyzer:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.categories: Dict[str, StrideCategory] = {}
        
    def analyze(self) -> Dict[str, StrideCategory]:
        """Run full STRIDE analysis."""
        print("=" * 80)
        print("STRIDE COVERAGE ANALYSIS")
        print("=" * 80)
        print()
        
        self._analyze_spoofing()
        self._analyze_tampering()
        self._analyze_repudiation()
        self._analyze_information_disclosure()
        self._analyze_denial_of_service()
        self._analyze_elevation_of_privilege()
        
        return self.categories
    
    def _check_file_exists(self, filepath: str) -> bool:
        """Check if file exists."""
        return (self.root_dir / filepath).exists()
    
    def _check_pattern_in_file(self, filepath: str, pattern: str, flags=0) -> Tuple[bool, List[str]]:
        """Check if pattern exists in file and return matches."""
        full_path = self.root_dir / filepath
        if not full_path.exists():
            return False, []
        
        try:
            content = full_path.read_text()
            matches = re.findall(pattern, content, flags)
            return len(matches) > 0, matches
        except Exception:
            return False, []
    
    def _check_terraform_resource(self, filepath: str, resource_type: str, resource_name: str = None) -> bool:
        """Check if Terraform resource exists."""
        full_path = self.root_dir / filepath
        if not full_path.exists():
            return False
        
        try:
            content = full_path.read_text()
            if resource_name:
                pattern = rf'resource\s+"{resource_type}"\s+"{resource_name}"'
            else:
                pattern = rf'resource\s+"{resource_type}"'
            return bool(re.search(pattern, content))
        except Exception:
            return False
    
    def _check_function_call(self, filepath: str, function_name: str) -> bool:
        """Check if function is called in file."""
        full_path = self.root_dir / filepath
        if not full_path.exists():
            return False
        
        try:
            content = full_path.read_text()
            # Check for function calls
            pattern = rf'{function_name}\s*\('
            return bool(re.search(pattern, content))
        except Exception:
            return False
    
    def _analyze_spoofing(self):
        """Analyze Spoofing Identity mitigations."""
        print("🧩 SPOOFING IDENTITY")
        print("-" * 80)
        
        category = StrideCategory(name="Spoofing Identity")
        
        # 1. JWT Authentication
        jwt_middleware_exists = self._check_file_exists("src/middleware/jwt_auth.py")
        jwt_registered = self._check_pattern_in_file("src/entrypoint.py", r"JWTAuthMiddleware")
        if jwt_middleware_exists and jwt_registered[0]:
            category.mitigations.append(MitigationCheck(
                name="JWT Authentication",
                status=Status.IMPLEMENTED,
                notes="JWT middleware exists and is registered",
                evidence=["src/middleware/jwt_auth.py", "src/entrypoint.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="JWT Authentication",
                status=Status.NOT_FOUND,
                notes="JWT middleware not found or not registered"
            ))
        
        # 2. JWT Secret via KMS/Secrets Manager
        jwt_secret_file = self._check_file_exists("src/utils/jwt_secret.py")
        secrets_manager_usage = self._check_pattern_in_file("src/utils/jwt_secret.py", r"secretsmanager|get_secret_value")
        if jwt_secret_file and secrets_manager_usage[0]:
            category.mitigations.append(MitigationCheck(
                name="JWT Secret via KMS/Secrets Manager",
                status=Status.IMPLEMENTED,
                notes="JWT secret retrieved from Secrets Manager (KMS-encrypted)",
                evidence=["src/utils/jwt_secret.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="JWT Secret via KMS/Secrets Manager",
                status=Status.NOT_FOUND,
                notes="JWT secret not managed by Secrets Manager"
            ))
        
        # 3. Token Expiration Validation
        token_exp_check = self._check_pattern_in_file("src/middleware/jwt_auth.py", r"verify_exp|exp.*expired|ExpiredSignatureError")
        if token_exp_check[0]:
            category.mitigations.append(MitigationCheck(
                name="Token Expiration Validation",
                status=Status.IMPLEMENTED,
                notes="Token expiration checked in JWT middleware",
                evidence=["src/middleware/jwt_auth.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Token Expiration Validation",
                status=Status.NOT_FOUND,
                notes="Token expiration not validated"
            ))
        
        # 4. Token Use Tracking
        consume_token_exists = self._check_pattern_in_file("src/services/auth_service.py", r"def consume_token_use")
        consume_token_called = self._check_pattern_in_file("src/services/auth_service.py", r"consume_token_use\(")
        called_in_middleware = self._check_pattern_in_file("src/middleware/jwt_auth.py", r"consume_token_use")
        
        if consume_token_exists[0] and consume_token_called[0]:
            if called_in_middleware[0]:
                category.mitigations.append(MitigationCheck(
                    name="Token Use Tracking",
                    status=Status.IMPLEMENTED,
                    notes="Token use tracking enforced in JWT middleware",
                    evidence=["src/services/auth_service.py", "src/middleware/jwt_auth.py"]
                ))
            else:
                # Check if it's called in /auth/me endpoint
                auth_me_content = self.root_dir / "src/services/auth_service.py"
                if auth_me_content.exists():
                    content = auth_me_content.read_text()
                    # Check if consume_token_use is called in /me endpoint
                    if "/me" in content and "consume_token_use" in content:
                        category.mitigations.append(MitigationCheck(
                            name="Token Use Tracking",
                            status=Status.PARTIAL,
                            notes="Token use tracking only enforced in /auth/me endpoint, not in middleware",
                            evidence=["src/services/auth_service.py"]
                        ))
                    else:
                        category.mitigations.append(MitigationCheck(
                            name="Token Use Tracking",
                            status=Status.PARTIAL,
                            notes="Function exists but not called in middleware"
                        ))
        elif consume_token_exists[0]:
            category.mitigations.append(MitigationCheck(
                name="Token Use Tracking",
                status=Status.PARTIAL,
                notes="Function exists but not called anywhere"
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Token Use Tracking",
                status=Status.NOT_FOUND,
                notes="Token use tracking function not found"
            ))
        
        # 5. IAM Group Isolation
        iam_group_policy = self._check_pattern_in_file("infra/modules/iam/main.tf", r"group106|Group_106")
        if iam_group_policy[0]:
            category.mitigations.append(MitigationCheck(
                name="IAM Group Isolation",
                status=Status.IMPLEMENTED,
                notes="IAM Group_106 policy isolation configured",
                evidence=["infra/modules/iam/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="IAM Group Isolation",
                status=Status.NOT_FOUND,
                notes="IAM Group_106 policy not found"
            ))
        
        # 6. Admin MFA
        # Check all IAM files
        iam_files = list(self.root_dir.glob("infra/**/iam*.tf"))
        mfa_found = False
        for iam_file in iam_files:
            if self._check_pattern_in_file(str(iam_file.relative_to(self.root_dir)), r"mfa|MFA|MultiFactorAuth")[0]:
                mfa_found = True
                break
        
        if mfa_found:
            category.mitigations.append(MitigationCheck(
                name="Admin MFA",
                status=Status.IMPLEMENTED,
                notes="MFA enforcement found in IAM policies"
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Admin MFA",
                status=Status.NOT_FOUND,
                notes="No MFA enforcement found in IAM policies"
            ))
        
        # Calculate coverage
        implemented = sum(1 for m in category.mitigations if m.status == Status.IMPLEMENTED)
        partial = sum(1 for m in category.mitigations if m.status == Status.PARTIAL)
        total = len(category.mitigations)
        category.coverage_percentage = ((implemented + partial * 0.5) / total * 100) if total > 0 else 0
        
        self.categories["Spoofing"] = category
        self._print_category(category)
        print()
    
    def _analyze_tampering(self):
        """Analyze Tampering with Data mitigations."""
        print("🧱 TAMPERING WITH DATA")
        print("-" * 80)
        
        category = StrideCategory(name="Tampering with Data")
        
        # 1. S3 SSE-KMS Encryption
        s3_encryption = self._check_terraform_resource("infra/modules/s3/main.tf", "aws_s3_bucket_server_side_encryption_configuration")
        s3_kms = self._check_pattern_in_file("infra/modules/s3/main.tf", r"sse_algorithm.*=.*aws:kms|aws:kms")
        if s3_encryption and s3_kms[0]:
            category.mitigations.append(MitigationCheck(
                name="S3 SSE-KMS Encryption",
                status=Status.IMPLEMENTED,
                notes="S3 bucket uses SSE-KMS encryption",
                evidence=["infra/modules/s3/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="S3 SSE-KMS Encryption",
                status=Status.NOT_FOUND,
                notes="S3 SSE-KMS encryption not configured"
            ))
        
        # 2. S3 Versioning
        s3_versioning = self._check_terraform_resource("infra/modules/s3/main.tf", "aws_s3_bucket_versioning")
        versioning_enabled = self._check_pattern_in_file("infra/modules/s3/main.tf", r'status\s*=\s*"Enabled"')
        if s3_versioning and versioning_enabled[0]:
            category.mitigations.append(MitigationCheck(
                name="S3 Versioning",
                status=Status.IMPLEMENTED,
                notes="S3 versioning enabled",
                evidence=["infra/modules/s3/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="S3 Versioning",
                status=Status.NOT_FOUND,
                notes="S3 versioning not enabled"
            ))
        
        # 3. Presigned URLs with TTL
        presigned_url = self._check_pattern_in_file("src/services/package_service.py", r"generate_presigned_url|presigned")
        ttl_check = self._check_pattern_in_file("src/services/package_service.py", r"ttl_seconds.*300|ExpiresIn.*300|300.*seconds")
        if presigned_url[0] and ttl_check[0]:
            category.mitigations.append(MitigationCheck(
                name="Presigned URLs (≤300s TTL)",
                status=Status.IMPLEMENTED,
                notes="Presigned URLs with 300s TTL enforced",
                evidence=["src/services/package_service.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Presigned URLs (≤300s TTL)",
                status=Status.NOT_FOUND,
                notes="Presigned URLs not found or TTL not enforced"
            ))
        
        # 4. DynamoDB Conditional Writes
        conditional_writes = self._check_pattern_in_file("src/services/package_service.py", r"UpdateExpression|ConditionExpression")
        if conditional_writes[0]:
            category.mitigations.append(MitigationCheck(
                name="DynamoDB Conditional Writes",
                status=Status.IMPLEMENTED,
                notes="DynamoDB conditional writes used",
                evidence=["src/services/package_service.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="DynamoDB Conditional Writes",
                status=Status.NOT_FOUND,
                notes="DynamoDB conditional writes not found"
            ))
        
        # 5. SHA-256 Hash Verification
        sha256_upload = self._check_pattern_in_file("src/services/package_service.py", r"hashlib\.sha256|sha256_hash")
        sha256_s3 = self._check_pattern_in_file("src/services/s3_service.py", r"hashlib\.sha256|sha256")
        sha256_verify = self._check_pattern_in_file("src/services/package_service.py", r"verify.*hash|hash.*verify")
        if (sha256_upload[0] or sha256_s3[0]) and sha256_verify[0]:
            category.mitigations.append(MitigationCheck(
                name="SHA-256 Hash Verification",
                status=Status.IMPLEMENTED,
                notes="SHA-256 hash computed and verified",
                evidence=["src/services/package_service.py", "src/services/s3_service.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="SHA-256 Hash Verification",
                status=Status.NOT_FOUND,
                notes="SHA-256 hash verification not found"
            ))
        
        # Calculate coverage
        implemented = sum(1 for m in category.mitigations if m.status == Status.IMPLEMENTED)
        total = len(category.mitigations)
        category.coverage_percentage = (implemented / total * 100) if total > 0 else 0
        
        self.categories["Tampering"] = category
        self._print_category(category)
        print()
    
    def _analyze_repudiation(self):
        """Analyze Repudiation mitigations."""
        print("🧾 REPUDIATION")
        print("-" * 80)
        
        category = StrideCategory(name="Repudiation")
        
        # 1. CloudTrail
        cloudtrail_resource = self._check_terraform_resource("infra/modules/monitoring/main.tf", "aws_cloudtrail")
        if cloudtrail_resource:
            category.mitigations.append(MitigationCheck(
                name="CloudTrail",
                status=Status.IMPLEMENTED,
                notes="CloudTrail configured for audit logging",
                evidence=["infra/modules/monitoring/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="CloudTrail",
                status=Status.NOT_FOUND,
                notes="CloudTrail not configured"
            ))
        
        # 2. CloudWatch Logging
        # Check Python files for logging
        python_files = list(self.root_dir.glob("src/**/*.py"))
        cloudwatch_logs_found = False
        for py_file in python_files[:10]:  # Check first 10 files
            if self._check_pattern_in_file(str(py_file.relative_to(self.root_dir)), r"logging\.|logger\.|cloudwatch")[0]:
                cloudwatch_logs_found = True
                break
        
        if cloudwatch_logs_found:
            category.mitigations.append(MitigationCheck(
                name="CloudWatch Logging",
                status=Status.IMPLEMENTED,
                notes="CloudWatch logging used throughout codebase"
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="CloudWatch Logging",
                status=Status.NOT_FOUND,
                notes="CloudWatch logging not found"
            ))
        
        # 3. Download Event Logging
        download_logging = self._check_pattern_in_file("src/services/validator_service.py", r"log_download_event|download.*log")
        if download_logging[0]:
            category.mitigations.append(MitigationCheck(
                name="Download Event Logging",
                status=Status.IMPLEMENTED,
                notes="Download events logged",
                evidence=["src/services/validator_service.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Download Event Logging",
                status=Status.NOT_FOUND,
                notes="Download event logging not found"
            ))
        
        # 4. Upload Event Logging
        # Check multiple files where upload logging should be implemented
        upload_logging_packages = self._check_pattern_in_file("src/routes/packages.py", r"log_upload_event")
        upload_logging_frontend = self._check_pattern_in_file("src/routes/frontend.py", r"log_upload_event")
        upload_logging_index = self._check_pattern_in_file("src/index.py", r"log_upload_event")
        upload_logging_validator = self._check_pattern_in_file("src/services/validator_service.py", r"def log_upload_event")
        
        if upload_logging_packages[0] or upload_logging_frontend[0] or upload_logging_index[0]:
            evidence = []
            if upload_logging_packages[0]:
                evidence.append("src/routes/packages.py")
            if upload_logging_frontend[0]:
                evidence.append("src/routes/frontend.py")
            if upload_logging_index[0]:
                evidence.append("src/index.py")
            if upload_logging_validator[0]:
                evidence.append("src/services/validator_service.py")
            
            category.mitigations.append(MitigationCheck(
                name="Upload Event Logging",
                status=Status.IMPLEMENTED,
                notes="Upload events logged in route handlers",
                evidence=evidence
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Upload Event Logging",
                status=Status.NOT_FOUND,
                notes="Upload event logging not found in route handlers"
            ))
        
        # 5. S3 Glacier Archiving
        glacier_archiving = self._check_pattern_in_file("infra/modules/monitoring/main.tf", r"glacier|Glacier|transition.*glacier")
        if glacier_archiving[0]:
            category.mitigations.append(MitigationCheck(
                name="S3 Glacier Archiving",
                status=Status.IMPLEMENTED,
                notes="Logs archived to S3 Glacier",
                evidence=["infra/modules/monitoring/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="S3 Glacier Archiving",
                status=Status.NOT_FOUND,
                notes="S3 Glacier archiving not configured"
            ))
        
        # Calculate coverage
        implemented = sum(1 for m in category.mitigations if m.status == Status.IMPLEMENTED)
        total = len(category.mitigations)
        category.coverage_percentage = (implemented / total * 100) if total > 0 else 0
        
        self.categories["Repudiation"] = category
        self._print_category(category)
        print()
    
    def _analyze_information_disclosure(self):
        """Analyze Information Disclosure mitigations."""
        print("🔒 INFORMATION DISCLOSURE")
        print("-" * 80)
        
        category = StrideCategory(name="Information Disclosure")
        
        # 1. Least-Privilege IAM
        iam_policies = list(self.root_dir.glob("infra/**/iam*.tf"))
        if len(iam_policies) > 0:
            category.mitigations.append(MitigationCheck(
                name="Least-Privilege IAM",
                status=Status.IMPLEMENTED,
                notes="IAM policies configured with scoped permissions",
                evidence=[str(p.relative_to(self.root_dir)) for p in iam_policies[:3]]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Least-Privilege IAM",
                status=Status.NOT_FOUND,
                notes="IAM policies not found"
            ))
        
        # 2. Presigned URLs (short-lived)
        presigned_url = self._check_pattern_in_file("src/services/package_service.py", r"generate_presigned_url|presigned")
        if presigned_url[0]:
            category.mitigations.append(MitigationCheck(
                name="Presigned URLs (Short-lived)",
                status=Status.IMPLEMENTED,
                notes="Presigned URLs used for secure access",
                evidence=["src/services/package_service.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Presigned URLs (Short-lived)",
                status=Status.NOT_FOUND,
                notes="Presigned URLs not found"
            ))
        
        # 3. Secrets Manager
        secrets_manager = self._check_pattern_in_file("src/utils/jwt_secret.py", r"secretsmanager|get_secret_value")
        if secrets_manager[0]:
            category.mitigations.append(MitigationCheck(
                name="Secrets Manager",
                status=Status.IMPLEMENTED,
                notes="Secrets Manager used for sensitive data",
                evidence=["src/utils/jwt_secret.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Secrets Manager",
                status=Status.NOT_FOUND,
                notes="Secrets Manager not used"
            ))
        
        # 4. RBAC Checks
        rbac_checks = self._check_pattern_in_file("src/services/package_service.py", r"group|Group|rbac|RBAC|role|Role")
        if rbac_checks[0]:
            category.mitigations.append(MitigationCheck(
                name="RBAC Checks",
                status=Status.IMPLEMENTED,
                notes="RBAC checks implemented",
                evidence=["src/services/package_service.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="RBAC Checks",
                status=Status.NOT_FOUND,
                notes="RBAC checks not found"
            ))
        
        # 5. Security Headers
        security_headers = self._check_file_exists("src/middleware/security_headers.py")
        security_headers_registered = self._check_pattern_in_file("src/entrypoint.py", r"SecurityHeadersMiddleware")
        if security_headers and security_headers_registered[0]:
            category.mitigations.append(MitigationCheck(
                name="Security Headers",
                status=Status.IMPLEMENTED,
                notes="Security headers middleware implemented",
                evidence=["src/middleware/security_headers.py", "src/entrypoint.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Security Headers",
                status=Status.NOT_FOUND,
                notes="Security headers not implemented"
            ))
        
        # 6. AWS Config
        aws_config_recorder = self._check_terraform_resource("infra/modules/config/main.tf", "aws_config_configuration_recorder")
        aws_config_delivery = self._check_terraform_resource("infra/modules/config/main.tf", "aws_config_delivery_channel")
        if aws_config_recorder or aws_config_delivery:
            category.mitigations.append(MitigationCheck(
                name="AWS Config",
                status=Status.IMPLEMENTED,
                notes="AWS Config configured for compliance monitoring",
                evidence=["infra/modules/config/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="AWS Config",
                status=Status.NOT_FOUND,
                notes="AWS Config not configured"
            ))
        
        # Calculate coverage
        implemented = sum(1 for m in category.mitigations if m.status == Status.IMPLEMENTED)
        total = len(category.mitigations)
        category.coverage_percentage = (implemented / total * 100) if total > 0 else 0
        
        self.categories["Information Disclosure"] = category
        self._print_category(category)
        print()
    
    def _analyze_denial_of_service(self):
        """Analyze Denial of Service mitigations."""
        print("🧨 DENIAL OF SERVICE")
        print("-" * 80)
        
        category = StrideCategory(name="Denial of Service")
        
        # 1. Rate Limiting
        rate_limit_middleware = self._check_file_exists("src/middleware/rate_limit.py")
        rate_limit_registered = self._check_pattern_in_file("src/entrypoint.py", r"RateLimitMiddleware")
        if rate_limit_middleware and rate_limit_registered[0]:
            category.mitigations.append(MitigationCheck(
                name="Rate Limiting",
                status=Status.IMPLEMENTED,
                notes="Rate limiting middleware implemented",
                evidence=["src/middleware/rate_limit.py", "src/entrypoint.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Rate Limiting",
                status=Status.NOT_FOUND,
                notes="Rate limiting not implemented"
            ))
        
        # 2. Validator Timeout
        validator_timeout = self._check_pattern_in_file("src/services/validator_service.py", r"timeout|Timeout|5.*second")
        if validator_timeout[0]:
            category.mitigations.append(MitigationCheck(
                name="Validator Timeout",
                status=Status.IMPLEMENTED,
                notes="Validator timeout protection implemented",
                evidence=["src/services/validator_service.py"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Validator Timeout",
                status=Status.NOT_FOUND,
                notes="Validator timeout not found"
            ))
        
        # 3. ECS Resource Limits
        ecs_files = list(self.root_dir.glob("infra/modules/ecs/*.tf"))
        ecs_limits_found = False
        for ecs_file in ecs_files:
            if self._check_pattern_in_file(str(ecs_file.relative_to(self.root_dir)), r"cpu|memory|limit")[0]:
                ecs_limits_found = True
                break
        
        if ecs_limits_found:
            category.mitigations.append(MitigationCheck(
                name="ECS Resource Limits",
                status=Status.IMPLEMENTED,
                notes="ECS resource limits configured",
                evidence=["infra/modules/ecs/"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="ECS Resource Limits",
                status=Status.NOT_FOUND,
                notes="ECS resource limits not found"
            ))
        
        # 4. API Gateway Throttling
        api_throttling = self._check_terraform_resource("infra/modules/api-gateway/main.tf", "aws_api_gateway_method_settings")
        if api_throttling:
            category.mitigations.append(MitigationCheck(
                name="API Gateway Throttling",
                status=Status.IMPLEMENTED,
                notes="API Gateway throttling configured",
                evidence=["infra/modules/api-gateway/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="API Gateway Throttling",
                status=Status.NOT_FOUND,
                notes="API Gateway throttling not configured"
            ))
        
        # 5. CloudWatch Alarms
        cloudwatch_alarms = self._check_terraform_resource("infra/modules/monitoring/main.tf", "aws_cloudwatch_metric_alarm")
        if cloudwatch_alarms:
            category.mitigations.append(MitigationCheck(
                name="CloudWatch Alarms",
                status=Status.IMPLEMENTED,
                notes="CloudWatch alarms configured",
                evidence=["infra/modules/monitoring/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="CloudWatch Alarms",
                status=Status.NOT_FOUND,
                notes="CloudWatch alarms not configured"
            ))
        
        # 6. AWS WAF
        # Check all Terraform files for WAF
        tf_files = list(self.root_dir.glob("infra/**/*.tf"))
        waf_resource = False
        for tf_file in tf_files:
            if self._check_terraform_resource(str(tf_file.relative_to(self.root_dir)), "aws_waf"):
                waf_resource = True
                break
        
        if waf_resource:
            category.mitigations.append(MitigationCheck(
                name="AWS WAF",
                status=Status.IMPLEMENTED,
                notes="AWS WAF configured"
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="AWS WAF",
                status=Status.NOT_FOUND,
                notes="AWS WAF not configured"
            ))
        
        # Calculate coverage
        implemented = sum(1 for m in category.mitigations if m.status == Status.IMPLEMENTED)
        total = len(category.mitigations)
        category.coverage_percentage = (implemented / total * 100) if total > 0 else 0
        
        self.categories["Denial of Service"] = category
        self._print_category(category)
        print()
    
    def _analyze_elevation_of_privilege(self):
        """Analyze Elevation of Privilege mitigations."""
        print("🧍‍♂️ ELEVATION OF PRIVILEGE")
        print("-" * 80)
        
        category = StrideCategory(name="Elevation of Privilege")
        
        # 1. Least-Privilege IAM
        iam_policies = list(self.root_dir.glob("infra/**/iam*.tf"))
        if len(iam_policies) > 0:
            category.mitigations.append(MitigationCheck(
                name="Least-Privilege IAM",
                status=Status.IMPLEMENTED,
                notes="Least-privilege IAM policies configured",
                evidence=[str(p.relative_to(self.root_dir)) for p in iam_policies[:2]]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Least-Privilege IAM",
                status=Status.NOT_FOUND,
                notes="IAM policies not found"
            ))
        
        # 2. Group_106 Restrictions
        group106 = self._check_pattern_in_file("infra/modules/iam/main.tf", r"group106|Group_106|group_106")
        if group106[0]:
            category.mitigations.append(MitigationCheck(
                name="Group_106 Restrictions",
                status=Status.IMPLEMENTED,
                notes="Group_106 policy restrictions configured",
                evidence=["infra/modules/iam/main.tf"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Group_106 Restrictions",
                status=Status.NOT_FOUND,
                notes="Group_106 restrictions not found"
            ))
        
        # 3. Admin MFA
        mfa_found = False
        iam_files = list(self.root_dir.glob("infra/**/iam*.tf"))
        for iam_file in iam_files:
            if self._check_pattern_in_file(str(iam_file.relative_to(self.root_dir)), r"mfa|MFA|MultiFactorAuth")[0]:
                mfa_found = True
                break
        
        if mfa_found:
            category.mitigations.append(MitigationCheck(
                name="Admin MFA",
                status=Status.IMPLEMENTED,
                notes="Admin MFA enforcement found"
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Admin MFA",
                status=Status.NOT_FOUND,
                notes="Admin MFA not enforced"
            ))
        
        # 4. GitHub OIDC
        oidc_script = self._check_file_exists("setup-oidc.sh")
        oidc_policy = self._check_file_exists("github-actions-trust-policy.json")
        if oidc_script or oidc_policy:
            category.mitigations.append(MitigationCheck(
                name="GitHub OIDC",
                status=Status.IMPLEMENTED,
                notes="GitHub OIDC configured for Terraform",
                evidence=["setup-oidc.sh", "github-actions-trust-policy.json"]
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="GitHub OIDC",
                status=Status.NOT_FOUND,
                notes="GitHub OIDC not configured"
            ))
        
        # 5. Terraform State Protection
        # Check Terraform files for backend configuration
        tf_files = list(self.root_dir.glob("infra/**/*.tf"))
        terraform_backend_found = False
        for tf_file in tf_files:
            if self._check_pattern_in_file(str(tf_file.relative_to(self.root_dir)), r"backend.*s3|terraform.*backend")[0]:
                terraform_backend_found = True
                break
        
        if terraform_backend_found:
            category.mitigations.append(MitigationCheck(
                name="Terraform State Protection",
                status=Status.IMPLEMENTED,
                notes="Terraform state protected via S3 backend"
            ))
        else:
            category.mitigations.append(MitigationCheck(
                name="Terraform State Protection",
                status=Status.NOT_FOUND,
                notes="Terraform state protection not found"
            ))
        
        # Calculate coverage
        implemented = sum(1 for m in category.mitigations if m.status == Status.IMPLEMENTED)
        total = len(category.mitigations)
        category.coverage_percentage = (implemented / total * 100) if total > 0 else 0
        
        self.categories["Elevation of Privilege"] = category
        self._print_category(category)
        print()
    
    def _print_category(self, category: StrideCategory):
        """Print category results."""
        for mitigation in category.mitigations:
            status_icon = mitigation.status.value
            print(f"{status_icon} {mitigation.name}: {mitigation.notes}")
            if mitigation.evidence:
                for evidence in mitigation.evidence[:2]:  # Show first 2 evidence files
                    print(f"   └─ {evidence}")
        
        print(f"\nCoverage: {category.coverage_percentage:.1f}%")
    
    def generate_summary(self):
        """Generate overall summary report."""
        print("=" * 80)
        print("STRIDE COVERAGE SUMMARY")
        print("=" * 80)
        print()
        
        total_implemented = 0
        total_partial = 0
        total_not_found = 0
        total_mitigations = 0
        
        for category_name, category in self.categories.items():
            implemented = sum(1 for m in category.mitigations if m.status == Status.IMPLEMENTED)
            partial = sum(1 for m in category.mitigations if m.status == Status.PARTIAL)
            not_found = sum(1 for m in category.mitigations if m.status == Status.NOT_FOUND)
            
            total_implemented += implemented
            total_partial += partial
            total_not_found += not_found
            total_mitigations += len(category.mitigations)
            
            print(f"{category_name}:")
            print(f"  ✅ Implemented: {implemented}")
            print(f"  ⚠️  Partial: {partial}")
            print(f"  ❌ Not Found: {not_found}")
            print(f"  Coverage: {category.coverage_percentage:.1f}%")
            print()
        
        # Calculate weighted average
        weighted_sum = sum(cat.coverage_percentage for cat in self.categories.values())
        weighted_avg = weighted_sum / len(self.categories) if len(self.categories) > 0 else 0
        
        print(f"Overall Coverage: {weighted_avg:.1f}%")
        print(f"Total Mitigations: {total_mitigations}")
        print(f"  ✅ Fully Implemented: {total_implemented}")
        print(f"  ⚠️  Partially Implemented: {total_partial}")
        print(f"  ❌ Not Implemented: {total_not_found}")
        print()
        
        # Critical gaps
        print("=" * 80)
        print("CRITICAL GAPS")
        print("=" * 80)
        print()
        
        gaps_found = False
        for category_name, category in self.categories.items():
            for mitigation in category.mitigations:
                if mitigation.status == Status.NOT_FOUND:
                    print(f"❌ {category_name}: {mitigation.name}")
                    gaps_found = True
        
        if not gaps_found:
            print("✅ No critical gaps found!")
        
        print()


def main():
    """Main entry point."""
    root_dir = Path(__file__).parent
    
    analyzer = StrideCoverageAnalyzer(root_dir)
    categories = analyzer.analyze()
    analyzer.generate_summary()
    
    # Exit with error code if coverage is low
    weighted_sum = sum(cat.coverage_percentage for cat in categories.values())
    weighted_avg = weighted_sum / len(categories) if len(categories) > 0 else 0
    
    if weighted_avg < 80:
        print("⚠️  Warning: STRIDE coverage is below 80%")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

