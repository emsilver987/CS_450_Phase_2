# 🔴 Risk Matrix - Trustworthy Module Registry

**Last Updated:** 2025-11-20  
**Project:** ACME Corporation - Trustworthy Module Registry  
**Phase:** 2 - Security Case Development

This document provides a comprehensive risk assessment matrix for all identified security risks, ranked by **Likelihood** and **Impact** using a 5-point scale.

---

## Risk Scoring Methodology

### Likelihood Scale (1-5)

- **1 - Very Low:** Extremely unlikely to occur
- **2 - Low:** Unlikely but possible
- **3 - Medium:** Could occur under certain conditions
- **4 - High:** Likely to occur
- **5 - Very High:** Almost certain to occur

### Impact Scale (1-5)

- **1 - Very Low:** Minimal impact, easily recoverable
- **2 - Low:** Minor impact, recoverable with effort
- **3 - Medium:** Moderate impact, requires remediation
- **4 - High:** Significant impact, service disruption or data exposure
- **5 - Critical:** Catastrophic impact, complete system compromise

### Risk Score Calculation

**Risk Score = Likelihood × Impact** (Range: 1-25)

### Risk Categories

- **🔴 Critical (20-25):** Must fix immediately before production
- **🟠 High (12-19):** Should fix soon, before production
- **🟡 Medium (6-11):** Fix in next release cycle
- **🟢 Low (1-5):** Fix when resources allow

---

## Risk Matrix Table

| ID        | Risk Description                        | STRIDE Category                           | Likelihood | Impact | Risk Score | Category    | Status           | Mitigation                                                  |
| --------- | --------------------------------------- | ----------------------------------------- | ---------- | ------ | ---------- | ----------- | ---------------- | ----------------------------------------------------------- |
| **R-001** | Missing WAF Protection                  | DoS, Information Disclosure               | 4          | 5      | **20**     | 🔴 Critical | ❌ Not Mitigated | Configure AWS WAF on API Gateway with managed rules         |
| **R-002** | JWT Secret Not Secured                  | Spoofing Identity                         | 3          | 5      | **15**     | 🟠 High     | ⚠️ Partial       | Function exists but middleware not using it                 |
| **R-003** | Admin MFA Not Enforced                  | Spoofing Identity, Elevation of Privilege | 3          | 5      | **15**     | 🟠 High     | ❌ Not Mitigated | Add IAM policy requiring MFA for admin group                |
| **R-004** | SSRF Protection Missing                 | Information Disclosure, Tampering         | 3          | 5      | **15**     | 🟠 High     | ❌ Not Mitigated | Add URL validation and internal network restrictions        |
| **R-005** | API Gateway Throttling Missing          | Denial of Service                         | 3          | 4      | **12**     | 🟠 High     | ❌ Not Mitigated | Configure API Gateway throttling limits                     |
| **R-006** | Token Use-Count Not Enforced            | Spoofing Identity                         | 2          | 5      | **10**     | 🟡 Medium   | ⚠️ Partial       | `consume_token_use()` exists but only called in `/auth/me`  |
| **R-007** | Security Headers Missing                | Information Disclosure                    | 3          | 3      | **9**      | 🟡 Medium   | ✅ **Mitigated** | Security headers middleware implemented                     |
| **R-008** | S3 Versioning Missing                   | Tampering                                 | 2          | 4      | **8**      | 🟡 Medium   | ❌ Not Mitigated | Enable S3 versioning in Terraform                           |
| **R-009** | CloudTrail Not Explicitly Configured    | Repudiation                               | 2          | 3      | **6**      | 🟡 Medium   | ❌ Not Mitigated | Add explicit CloudTrail trail in Terraform                  |
| **R-010** | CloudWatch Alarms Missing               | Denial of Service                         | 2          | 3      | **6**      | 🟡 Medium   | ✅ **Mitigated** | CloudWatch alarms configured in monitoring module           |
| **R-011** | Upload Event Logging Missing            | Repudiation                               | 2          | 3      | **6**      | 🟡 Medium   | ⚠️ Partial       | Upload event logging function exists but needs verification |
| **R-012** | AWS Config Not Configured               | Information Disclosure                    | 2          | 2      | **4**      | 🟢 Low      | ✅ **Mitigated** | AWS Config configured in config module                      |
| **R-013** | Log Archiving Missing                   | Repudiation                               | 1          | 2      | **2**      | 🟢 Low      | ❌ Not Mitigated | Add S3 lifecycle policy for Glacier archiving               |
| **R-014** | Validator Script Integrity Verification | Tampering                                 | 1          | 2      | **2**      | 🟢 Low      | ❌ Not Mitigated | Add checksums for validator scripts                         |

---

## Risk Heat Map

```
Impact →
        1    2    3    4    5
L  5    🟢   🟢   🟡   🟠   🔴
i  4    🟢   🟢   🟡   🟠   🔴  R-001
k  3    🟢   🟢   🟡   🟠   🟠  R-002, R-003, R-004
e  2    🟢   🟢   🟡   🟡   🟡  R-006, R-008
l  1    🟢   🟢   🟢   🟢   🟢  R-013, R-014
i
h
o
o
d
```

---

## Detailed Risk Descriptions

### 🔴 Critical Risks (Must Fix Before Production)

#### R-001: Missing WAF Protection

- **STRIDE Categories:** Denial of Service, Information Disclosure
- **Description:** No AWS WAF protection configured on API Gateway, leaving the system vulnerable to common web attacks (SQL injection, XSS, rate-based DoS)
- **Attack Vector:** Automated scanners and malicious actors can exploit exposed API endpoints
- **Business Impact:** Service compromise, data breach, reputation damage
- **Current State:** No WAF configuration found in Terraform
- **Mitigation Plan:**
  1. Configure AWS WAF on API Gateway
  2. Add AWS Managed Rules (Core Rule Set, Known Bad Inputs)
  3. Add rate-based rules for DoS protection
  4. Test with sample attack patterns
- **Testability:** Yes (penetration testing, WAF rule testing)
- **Priority:** P0 - Critical

---

### 🟠 High Risks (Should Fix Soon)

#### R-002: JWT Secret Not Secured

- **STRIDE Category:** Spoofing Identity
- **Description:** JWT secret stored as plain environment variable (`JWT_SECRET`), can be leaked via logs, config files, or environment inspection
- **Attack Vector:** If secret is leaked, attackers can forge any JWT token
- **Business Impact:** Complete authentication bypass, unauthorized access to all endpoints
- **Current State:** ⚠️ **Partial** - `get_jwt_secret()` function exists in `src/utils/jwt_secret.py` to retrieve from Secrets Manager, but middleware still uses `os.getenv("JWT_SECRET")` directly (line 53 in `src/middleware/jwt_auth.py`)
- **Remaining Work:**
  1. Update JWT middleware to use `get_jwt_secret()` instead of `os.getenv("JWT_SECRET")`
  2. Ensure Secrets Manager secret exists and IAM policies allow access
  3. Remove `JWT_SECRET` env var dependency for production
- **Testability:** Yes (code review, secret scanning)
- **Priority:** P1 - High

#### R-003: Admin MFA Not Enforced

- **STRIDE Categories:** Spoofing Identity, Elevation of Privilege
- **Description:** Admin accounts can be compromised without MFA requirement, allowing privilege escalation
- **Attack Vector:** Credential stuffing, phishing attacks on admin accounts
- **Business Impact:** Full system compromise, data breach, service disruption
- **Current State:** No MFA enforcement found in IAM policies
- **Mitigation Plan:**
  1. Create IAM policy requiring MFA for admin group
  2. Add condition: `aws:MultiFactorAuthPresent: true`
  3. Test MFA enforcement
  4. Document MFA setup process for admins
- **Testability:** Yes (IAM policy review, manual testing)
- **Priority:** P1 - High

#### R-004: SSRF Protection Missing

- **STRIDE Categories:** Information Disclosure, Tampering
- **Description:** No Server-Side Request Forgery (SSRF) protection, allowing attackers to make requests to internal resources
- **Attack Vector:** If URLs are user-controlled, attackers can access internal networks, metadata service (169.254.169.254)
- **Business Impact:** Internal network access, metadata service compromise, data exfiltration
- **Current State:** No URL validation or internal network restrictions found
- **Mitigation Plan:**
  1. Add URL validation middleware
  2. Block internal network access (169.254.169.254, localhost, private IPs)
  3. Whitelist allowed domains if applicable
  4. Add SSRF tests
- **Testability:** Yes (penetration testing, SSRF test cases)
- **Priority:** P1 - High

#### R-005: API Gateway Throttling Missing

- **STRIDE Category:** Denial of Service
- **Description:** Application-level rate limiting exists, but API Gateway throttling not configured, allowing DoS attacks to bypass application limits
- **Attack Vector:** Distributed DoS attacks can overwhelm the system
- **Business Impact:** Service unavailability, degraded performance
- **Current State:** Rate limiting at application layer (120 req/60s), no API Gateway throttling
- **Mitigation Plan:**
  1. Configure API Gateway throttling in Terraform
  2. Set throttling limits (requests per second, burst)
  3. Configure per-account and per-key limits
  4. Test throttling functionality
- **Testability:** Yes (load testing, throttling verification)
- **Priority:** P1 - High

---

### 🟡 Medium Risks (Fix in Next Release)

#### R-006: Token Use-Count Not Enforced

- **STRIDE Category:** Spoofing Identity
- **Description:** Tokens can be reused indefinitely within expiration period, despite documentation claiming "1,000 uses max"
- **Attack Vector:** Captured tokens can be reused multiple times
- **Business Impact:** Unauthorized access, token replay attacks
- **Status:** ⚠️ **Partial** - `consume_token_use()` function exists and is implemented, but only called in `/auth/me` endpoint (line 331 in `src/services/auth_service.py`). Not enforced in JWT middleware or `verify_auth_token()` helper.
- **Remaining Work:**
  1. Call `consume_token_use()` in JWT middleware or `verify_auth_token()` helper for all protected endpoints
  2. Enforce 1,000 use limit globally
  3. OR: Remove use-count claim from documentation if not implementing globally
- **Testability:** Yes (functional testing)
- **Priority:** P2 - Medium

#### R-007: Security Headers Missing

- **STRIDE Category:** Information Disclosure
- **Description:** Missing security headers (HSTS, X-Content-Type-Options, X-Frame-Options) leaves clients vulnerable to browser-based attacks
- **Attack Vector:** XSS, clickjacking, MIME-type confusion attacks
- **Business Impact:** Client-side attacks, user data compromise
- **Status:** ✅ **Mitigated**
- **Mitigation Implemented:**
  1. ✅ Security headers middleware implemented in `src/middleware/security_headers.py`
  2. ✅ Adds HSTS, X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy, Permissions-Policy
  3. ✅ Middleware registered in application
- **Implementation:** `SecurityHeadersMiddleware` in `src/middleware/security_headers.py` adds comprehensive security headers to all responses
- **Testability:** Yes (header verification, browser testing)
- **Priority:** P2 - Medium

#### R-008: S3 Versioning Missing

- **STRIDE Category:** Tampering
- **Description:** Cannot recover from accidental or malicious overwrites of package files
- **Attack Vector:** Accidental overwrites, malicious modifications
- **Business Impact:** Data loss, inability to recover previous versions
- **Current State:** No `aws_s3_bucket_versioning` resource found in `infra/modules/s3/main.tf`
- **Mitigation Plan:**
  1. Add `aws_s3_bucket_versioning` resource to `infra/modules/s3/main.tf`
  2. Set `status = "Enabled"` on artifacts bucket
  3. Configure lifecycle policies for old versions (optional, for cost optimization)
  4. Test version recovery functionality
- **Note:** Document previously claimed this was mitigated, but verification shows it's not in the code
- **Testability:** Yes (configuration review, version recovery testing)
- **Priority:** P2 - Medium

#### R-009: CloudTrail Not Explicitly Configured

- **STRIDE Category:** Repudiation
- **Description:** Relies on AWS account-level CloudTrail defaults, may not capture all events or be configured optimally
- **Attack Vector:** Audit trail gaps, incomplete forensics
- **Business Impact:** Compliance issues, incomplete audit trail
- **Current State:** No CloudTrail resource found in `infra/modules/monitoring/main.tf`. Plan output shows it's planned but not in actual code.
- **Mitigation Plan:**
  1. Create explicit CloudTrail trail in Terraform (`infra/modules/monitoring/main.tf`)
  2. Configure S3 bucket for log storage
  3. Enable log file validation
  4. Configure log retention and Glacier archiving
- **Note:** Terraform plan output shows CloudTrail is planned but resource doesn't exist in actual code
- **Testability:** Yes (configuration review, CloudTrail log verification)
- **Priority:** P2 - Medium

#### R-010: CloudWatch Alarms Missing

- **STRIDE Category:** Denial of Service
- **Description:** Cannot automatically detect and respond to DoS patterns or performance degradation
- **Attack Vector:** DoS attacks may go undetected until manual intervention
- **Business Impact:** Delayed incident response, extended service disruption
- **Status:** ✅ **Mitigated**
- **Mitigation Implemented:**
  1. ✅ Three CloudWatch alarms configured in `infra/modules/monitoring/main.tf`
  2. ✅ `validator-high-cpu` alarm (CPU > 80%)
  3. ✅ `validator-high-memory` alarm (Memory > 80%)
  4. ✅ `validator-task-count` alarm (Running tasks < 1)
- **Implementation:** CloudWatch alarms configured in `infra/modules/monitoring/main.tf` with thresholds for CPU, memory, and task count monitoring
- **Testability:** Yes (configuration review, alarm testing)
- **Priority:** P2 - Medium

#### R-011: Upload Event Logging Missing

- **STRIDE Category:** Repudiation
- **Description:** Cannot prove who uploaded what package, only downloads are logged
- **Attack Vector:** Users can deny uploading malicious packages
- **Business Impact:** Non-repudiation gaps, compliance issues
- **Status:** ⚠️ **Partial** - Function exists but needs verification in actual upload endpoints
- **Current State:** `log_upload_event()` function documented but needs verification that it's called in upload endpoints
- **Remaining Work:**
  1. Verify `log_upload_event()` is called in `/init`, `/commit`, and `/abort` endpoints
  2. Ensure events are logged to DynamoDB with user_id, timestamp, package info
  3. Test logging functionality
- **Testability:** Yes (functional testing, log verification)
- **Priority:** P2 - Medium

---

### 🟢 Low Risks (Fix When Resources Allow)

#### R-012: AWS Config Not Configured

- **STRIDE Category:** Information Disclosure
- **Description:** Cannot detect policy drift or configuration changes automatically
- **Attack Vector:** Configuration changes may go undetected
- **Business Impact:** Compliance monitoring gaps
- **Status:** ✅ **Mitigated**
- **Mitigation Implemented:**
  1. ✅ AWS Config fully configured in `infra/modules/config/main.tf`
  2. ✅ Configuration recorder enabled with all supported resource types
  3. ✅ Delivery channel configured with S3 bucket for snapshots
  4. ✅ S3 bucket for Config snapshots with KMS encryption and versioning
  5. ✅ IAM role and policies configured for Config service
- **Implementation:** AWS Config module (`infra/modules/config/main.tf`) includes configuration recorder, delivery channel, S3 bucket, and IAM roles
- **Testability:** Yes (configuration review)
- **Priority:** P3 - Low

#### R-013: Log Archiving Missing

- **STRIDE Category:** Repudiation
- **Description:** Logs may be deleted before compliance retention period
- **Attack Vector:** Log retention policy violations
- **Business Impact:** Compliance requirement gaps
- **Current State:** No S3 lifecycle policy for Glacier archiving
- **Mitigation Plan:**
  1. Create S3 lifecycle policy
  2. Configure Glacier transition (e.g., after 90 days)
  3. Document retention policy
  4. Test archiving process
- **Testability:** Yes (configuration review, archiving test)
- **Priority:** P3 - Low

#### R-014: Validator Script Integrity Verification

- **STRIDE Category:** Tampering
- **Description:** Validator scripts stored in S3 could be tampered with (low risk due to IAM protection)
- **Attack Vector:** Unauthorized S3 access (mitigated by IAM)
- **Business Impact:** Integrity concern (low impact due to existing controls)
- **Current State:** No checksums for validator scripts
- **Mitigation Plan:**
  1. Add checksums for validator scripts
  2. Verify checksums before execution
  3. Store checksums in DynamoDB
  4. Test integrity verification
- **Testability:** Yes (functional testing)
- **Priority:** P3 - Low

---

## Risk Summary Statistics

| Category    | Count  | Percentage | Mitigation Status                   |
| ----------- | ------ | ---------- | ----------------------------------- |
| 🔴 Critical | 1      | 7.1%       | ❌ 0% mitigated                     |
| 🟠 High     | 4      | 28.6%      | ⚠️ 25% partially mitigated          |
| 🟡 Medium   | 6      | 42.9%      | ✅ 33% mitigated, ⚠️ 17% partial    |
| 🟢 Low      | 3      | 21.4%      | ✅ 33% mitigated                    |
| **Total**   | **14** | **100%**   | **✅ 21% mitigated, ⚠️ 7% partial** |

---

## Risk Mitigation Roadmap

### Phase 1: Critical & High Risks (Weeks 1-2)

- [ ] R-001: Configure AWS WAF
- [ ] R-002: Migrate JWT secret to Secrets Manager
- [ ] R-003: Enforce admin MFA
- [ ] R-004: Implement SSRF protection
- [ ] R-005: Configure API Gateway throttling

### Phase 2: Medium Risks (Weeks 3-4)

- [ ] R-006: Implement token use-count OR update documentation
- [x] R-007: Add security headers middleware ✅ **COMPLETED**
- [ ] R-008: Enable S3 versioning
- [ ] R-009: Configure explicit CloudTrail trail
- [x] R-010: Add CloudWatch alarms ✅ **COMPLETED**
- [ ] R-011: Verify upload event logging implementation

### Phase 3: Low Risks (Week 5+)

- [x] R-012: Configure AWS Config ✅ **COMPLETED**
- [ ] R-013: Add log archiving to Glacier
- [ ] R-014: Add validator script integrity verification

---

## Related Documentation

- [STRIDE Coverage Analysis](./docs/security/STRIDE_COVERAGE_ANALYSIS.md) - Implementation status of STRIDE mitigations
- [Security Audit Report](./docs/security/SECURITY_AUDIT_REPORT.md) - Comprehensive security audit findings
- [Vulnerability Traceability](./VULNERABILITY_TRACEABILITY.md) - Mapping of vulnerabilities to fixes and tests
- [STRIDE Threat Model](./docs/security/stride-threat-level.md) - Detailed threat model documentation

---

_This risk matrix should be reviewed and updated quarterly or after significant security changes._
