# Security Review Report
**Branch:** `tests_p`  
**Base Branch:** `main`  
**Date:** 2025-01-27

## Executive Summary

This security review examines changes on the `tests_p` branch, which includes significant security enhancements:
- JWT authentication middleware with token use-count tracking
- Rate limiting middleware
- Security headers middleware
- AWS Secrets Manager integration for secrets
- WAF (Web Application Firewall) integration
- Enhanced logging and audit capabilities

**Overall Assessment:** ✅ **Mostly Secure** with some recommendations

---

## 1. Authentication & Sessions

### ✅ **Strengths:**
1. **JWT Implementation** (`src/middleware/jwt_auth.py`):
   - Uses HS256 algorithm with secret from AWS Secrets Manager
   - Enforces `exp` claim requirement
   - Validates issuer/audience when configured
   - Implements token use-count tracking via DynamoDB

2. **Token Use-Count Enforcement**:
   - Tokens tracked in DynamoDB with `remaining_uses` counter
   - Token consumption checked on each request
   - Prevents token replay attacks

3. **Secret Management**:
   - JWT secrets stored in AWS Secrets Manager (KMS-encrypted)
   - Production mode fails fast if Secrets Manager unavailable
   - Development fallback to env vars (acceptable for local dev)

### ⚠️ **Issues & Recommendations:**

1. **CRITICAL: Token Storage in DynamoDB** (`src/services/auth_service.py:122`):
   ```python
   "token": token,  # Full JWT stored in DynamoDB
   ```
   - **Issue:** Full JWT tokens stored in DynamoDB table
   - **Risk:** If DynamoDB is compromised, attackers get valid tokens
   - **Recommendation:** Store only `jti` (token ID) and metadata, not the full token
   - **Priority:** HIGH

2. **Static Token in Code** (`src/services/auth_public.py:31-35`):
   ```python
   STATIC_TOKEN = (
       "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
       "eyJzdWIiOiJlY2UzMDg2MWRlZmF1bHRhZG1pbnVzZXIiLCJpc19hZG1pbiI6dHJ1ZX0."
       "example"
   )
   ```
   - **Issue:** Hardcoded static token for autograder compatibility
   - **Risk:** If this token is valid, it bypasses normal auth
   - **Recommendation:** Verify this token is actually invalid (signature is "example")
   - **Priority:** MEDIUM

3. **Session Storage:**
   - **Status:** No session storage (stateless JWT)
   - **Note:** This is fine, but ensure token revocation works via DynamoDB deletion

---

## 2. Authorization & Access Control

### ✅ **Strengths:**
1. **Middleware-Based Auth**:
   - JWT middleware runs before routes
   - Exempt paths clearly defined
   - Consistent auth enforcement

2. **Role-Based Access**:
   - User roles stored in JWT claims
   - Roles accessible via `request.state.user`

### ⚠️ **Issues & Recommendations:**

1. **Artifact Endpoints Exempt** (`src/middleware/jwt_auth.py:29`):
   ```python
   "/artifact/",  # Temporarily exempt all artifact endpoints
   ```
   - **Issue:** All artifact endpoints bypass authentication
   - **Risk:** Unauthorized access to artifacts
   - **Recommendation:** Remove this exemption or make it conditional
   - **Priority:** HIGH

2. **Server-Side Authorization Checks**:
   - **Status:** Need to verify all sensitive endpoints check `request.state.user` roles
   - **Recommendation:** Audit all routes to ensure server-side role checks
   - **Priority:** MEDIUM

3. **Admin Password Hardcoded Fallback** (`src/utils/admin_password.py:24-25`):
   ```python
   _DEFAULT_PRIMARY = "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages"
   _DEFAULT_ALTERNATE = "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
   ```
   - **Issue:** Hardcoded passwords in code (development fallback)
   - **Risk:** If code is leaked, passwords are exposed
   - **Recommendation:** Use environment variables even for dev fallback
   - **Priority:** LOW (only affects dev mode)

---

## 3. Data Protection

### ✅ **Strengths:**
1. **Secrets Management**:
   - JWT secrets in AWS Secrets Manager (KMS-encrypted)
   - Admin passwords in Secrets Manager
   - Production mode enforces Secrets Manager usage

2. **Encryption in Transit**:
   - HTTPS enforced via security headers (HSTS)
   - API Gateway should enforce HTTPS

3. **Encryption at Rest**:
   - S3 buckets use SSE-KMS encryption
   - DynamoDB encryption at rest (verify in Terraform)

### ⚠️ **Issues & Recommendations:**

1. **Password Storage** (`src/services/auth_service.py:192`):
   ```python
   "password_hash": hash_password(user_data.password),
   ```
   - **Status:** ✅ Using bcrypt (good)
   - **Note:** Ensure bcrypt cost factor is appropriate (default is usually fine)

2. **Sensitive Data in Logs**:
   - **Status:** Logging redaction tests exist (`tests/unit/test_logging_redaction.py`)
   - **Recommendation:** Verify redaction is actually implemented in production logging
   - **Priority:** MEDIUM

3. **Token in DynamoDB**:
   - **Issue:** Full JWT stored in DynamoDB (see Section 1)
   - **Recommendation:** Remove token storage, keep only metadata

---

## 4. Input Validation & Output Encoding

### ✅ **Strengths:**
1. **File Upload Validation**:
   - ZIP structure validation (`src/services/package_service.py:78`)
   - HuggingFace structure validation (`src/services/s3_service.py:104`)
   - File size limits in WAF (10MB body, 8KB URI/query)

2. **Query Parameter Validation**:
   - Pydantic models for request validation
   - Type checking on query parameters

3. **Security Headers**:
   - CSP (Content Security Policy) implemented
   - XSS protection headers
   - Frame options (clickjacking protection)

### ⚠️ **Issues & Recommendations:**

1. **CSP Permissive Default** (`src/middleware/security_headers.py:69-77`):
   ```python
   "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
   "style-src 'self' 'unsafe-inline'; "
   ```
   - **Issue:** `unsafe-inline` and `unsafe-eval` weaken XSS protection
   - **Recommendation:** Tighten CSP for production (remove unsafe-* if possible)
   - **Priority:** MEDIUM

2. **Regex Injection Risk** (`src/routes/packages.py:82`):
   ```python
   escaped_query = re.escape(q)
   name_regex = f".*{escaped_query}.*"
   ```
   - **Status:** ✅ Properly escaped
   - **Note:** Good practice

3. **File Upload Size Limits**:
   - **Status:** WAF enforces 10MB body limit
   - **Recommendation:** Verify application-level limits match WAF limits
   - **Priority:** LOW

4. **SQL Injection** (if using SQL):
   - **Status:** Using DynamoDB (NoSQL), so SQL injection not applicable
   - **Note:** DynamoDB queries use parameterized expressions (good)

---

## 5. Dependencies & Third Parties

### ✅ **Changes in `requirements.txt`:**
- `jinja2`: 3.1.4 → 3.1.6 (patch update)
- `python-multipart`: 0.0.6 → >=0.0.18 (major update)
- `requests`: 2.32.3 → 2.32.4 (patch update)
- `httpx`: NEW dependency

### ⚠️ **Issues & Recommendations:**

1. **python-multipart Major Update**:
   - **Issue:** Jump from 0.0.6 to >=0.0.18 (major version change)
   - **Risk:** Potential breaking changes or new vulnerabilities
   - **Recommendation:** 
     - Pin to specific version (e.g., `0.0.18`)
     - Test file upload functionality thoroughly
     - Review changelog for security fixes
   - **Priority:** MEDIUM

2. **New Dependency: httpx**:
   - **Issue:** New dependency added
   - **Recommendation:** 
     - Verify it's from trusted source (it is - maintained by encode)
     - Check for known vulnerabilities
     - Document why it's needed
   - **Priority:** LOW

3. **Dependency Audit**:
   - **Recommendation:** Run `pip-audit` or `safety check` regularly
   - **Priority:** LOW (maintenance)

---

## 6. API & Endpoints

### ✅ **Strengths:**
1. **Rate Limiting**:
   - In-memory rate limiter (120 req/min default)
   - Configurable via environment variables
   - IP-based limiting

2. **WAF Integration**:
   - AWS WAF with managed rules (OWASP Top 10)
   - Rate-based rules for DoS protection
   - Size restrictions

3. **Error Messages**:
   - Generic error messages (don't leak internal details)
   - No stack traces in production responses

### ⚠️ **Issues & Recommendations:**

1. **Rate Limiter In-Memory** (`src/middleware/rate_limit.py`):
   - **Issue:** In-memory rate limiter doesn't work across multiple instances
   - **Risk:** Rate limits can be bypassed with multiple servers
   - **Recommendation:** 
     - Use Redis/DynamoDB for distributed rate limiting
     - Or rely on API Gateway/WAF rate limiting
   - **Priority:** MEDIUM

2. **New Endpoints**:
   - `/auth/register` - Public (acceptable)
   - `/auth/login` - Public (acceptable)
   - `/auth/me` - Protected (good)
   - `/auth/logout` - Protected (good)
   - `/authenticate` - Public (autograder compatibility)

3. **Rate Limit Configuration**:
   - **Status:** Configurable via env vars with validation
   - **Note:** Good bounds checking (max 10000 requests, max 3600s window)

---

## 7. Configuration & Secrets

### ✅ **Strengths:**
1. **Secrets in Secrets Manager**:
   - JWT secrets: `acme-jwt-secret`
   - Admin passwords: `ece30861defaultadminuser`
   - KMS-encrypted storage

2. **Environment Variables**:
   - Sensitive config via env vars (not hardcoded)
   - Production/development mode detection

### ⚠️ **Issues & Recommendations:**

1. **Secret Caching** (`src/utils/jwt_secret.py:19`):
   ```python
   _JWT_SECRET_CACHE: Optional[str] = None
   ```
   - **Issue:** Secret cached in memory for lifetime of process
   - **Risk:** If secret is rotated, app won't pick it up until restart
   - **Recommendation:** 
     - Add TTL to cache (e.g., 1 hour)
     - Or implement secret rotation handling
   - **Priority:** LOW (acceptable for now)

2. **Default Secret Generation** (`src/utils/jwt_secret.py:167-174`):
   ```python
   fallback_secret = secrets_module.token_urlsafe(32)
   ```
   - **Issue:** Generates temporary secret in dev mode
   - **Risk:** If used in production, tokens won't be valid across restarts
   - **Status:** ✅ Only in development mode (acceptable)
   - **Priority:** LOW

3. **Configuration Validation**:
   - **Status:** Rate limit config has validation
   - **Recommendation:** Add validation for other critical configs
   - **Priority:** LOW

---

## 8. Infrastructure & Networking

### ✅ **Strengths:**
1. **WAF Configuration** (`infra/modules/waf/main.tf`):
   - AWS Managed Rules (OWASP Top 10)
   - Rate-based rules
   - Size restrictions
   - CloudWatch metrics enabled

2. **S3 Security**:
   - Private buckets
   - SSE-KMS encryption
   - Public access blocked
   - Versioning enabled

3. **IAM Policies**:
   - Least privilege principle (verify in Terraform)
   - Service-specific roles

### ⚠️ **Issues & Recommendations:**

1. **WAF Logging Disabled** (`infra/modules/waf/main.tf:314-320`):
   ```terraform
   # resource "aws_wafv2_web_acl_logging_configuration" "main" {
   #   ...
   # }
   ```
   - **Issue:** WAF logging commented out
   - **Risk:** Can't investigate WAF blocks/attacks
   - **Recommendation:** Enable WAF logging via Kinesis Firehose
   - **Priority:** MEDIUM

2. **API Gateway Throttling**:
   - **Status:** Need to verify API Gateway has throttling configured
   - **Recommendation:** Check `infra/modules/api-gateway/main.tf` for throttling
   - **Priority:** MEDIUM

3. **Network Security**:
   - **Status:** Need to verify security groups restrict access
   - **Recommendation:** Audit security group rules
   - **Priority:** MEDIUM

---

## 9. Logging, Monitoring & Alerts

### ✅ **Strengths:**
1. **Audit Logging**:
   - Upload events logged (`src/services/validator_service.py:195`)
   - Download events logged
   - User ID extraction for audit trail

2. **CloudWatch Integration**:
   - WAF metrics to CloudWatch
   - Application logs (verify configuration)

3. **Logging Redaction**:
   - Tests for redaction exist
   - Need to verify implementation in production

### ⚠️ **Issues & Recommendations:**

1. **Logging Redaction Implementation**:
   - **Status:** Tests exist, but need to verify actual middleware
   - **Recommendation:** Check if `LoggingMiddleware` in `src/index.py` implements redaction
   - **Priority:** MEDIUM

2. **Sensitive Data in Logs**:
   - **Recommendation:** Audit all log statements to ensure no secrets/tokens logged
   - **Priority:** MEDIUM

3. **CloudTrail Configuration**:
   - **Status:** Need to verify CloudTrail is enabled for API calls
   - **Recommendation:** Check Terraform for CloudTrail configuration
   - **Priority:** LOW

---

## 10. Privacy & Compliance

### ✅ **Status:**
- No new privacy-impacting features identified
- No additional data collection
- Existing user data handling unchanged

### ⚠️ **Recommendations:**
1. **Privacy Policy**:
   - **Recommendation:** Ensure privacy policy covers JWT token storage and use
   - **Priority:** LOW

---

## Summary of Critical Issues

### 🔴 **HIGH PRIORITY:**
1. **Token Storage in DynamoDB** - Remove full JWT from DynamoDB, store only metadata
2. **Artifact Endpoints Exempt** - Remove or conditionally apply auth exemption

### 🟡 **MEDIUM PRIORITY:**
1. **Rate Limiter Distribution** - Use distributed rate limiting (Redis/DynamoDB)
2. **CSP Configuration** - Tighten Content Security Policy
3. **WAF Logging** - Enable WAF logging for security monitoring
4. **Logging Redaction** - Verify redaction is implemented in production

### 🟢 **LOW PRIORITY:**
1. **Secret Cache TTL** - Add TTL to secret cache for rotation support
2. **Dependency Pinning** - Pin `python-multipart` to specific version
3. **Configuration Validation** - Add validation for more configs

---

## Recommendations for Next Steps

1. **Immediate Actions:**
   - Remove full JWT token from DynamoDB storage
   - Review and fix artifact endpoint authentication exemption
   - Verify logging redaction is implemented

2. **Short-term (1-2 weeks):**
   - Implement distributed rate limiting
   - Enable WAF logging
   - Tighten CSP configuration

3. **Long-term (1+ month):**
   - Add secret rotation support
   - Implement comprehensive dependency scanning
   - Add security monitoring and alerting

---

## Conclusion

The `tests_p` branch introduces significant security improvements:
- ✅ Strong authentication with JWT and token use-count tracking
- ✅ Secrets management via AWS Secrets Manager
- ✅ Rate limiting and WAF protection
- ✅ Security headers implementation

However, there are **2 high-priority issues** that should be addressed before merging:
1. Storing full JWT tokens in DynamoDB
2. Artifact endpoints bypassing authentication

Once these are fixed, the branch should be ready for merge from a security perspective.

