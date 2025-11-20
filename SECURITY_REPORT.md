# STRIDE Security Analysis Report
**System:** ACME Package Registry  
**Date:** 2025-11-20  
**Target:** Source Code (`src/`)  

---

## 1. Executive Summary
This report details the findings of a STRIDE security analysis performed on the ACME Package Registry system. The analysis identified critical vulnerabilities in Authentication, Logging, and Input Validation. The most severe issues include potential token leakage in logs, lack of token revocation checks, and Denial of Service (DoS) vectors via Regex and File Uploads.

## 2. System Architecture & Trust Boundaries
The system consists of a FastAPI backend, a Jinja2-based frontend, and AWS services (S3, DynamoDB).

**Trust Boundaries:**
1.  **Public Boundary:** The interface between the Internet and the FastAPI application (Routes).
2.  **Data Boundary:** The interface between the FastAPI application and the Data Store (DynamoDB) / Object Store (S3).
3.  **Admin Boundary:** The separation between standard user functions and administrative functions (e.g., `/reset`).

## 3. STRIDE Analysis Findings

### 3.1 Spoofing (Identity)
*   **Threat:** **Token Revocation Bypass**
    *   **Severity:** High
    *   **Description:** The `JWTAuthMiddleware` and `require_auth` functions verify the JWT signature but do not consistently validate the token against the DynamoDB `tokens` table.
    *   **Impact:** A user can continue to use a token even after it has been revoked (e.g., via logout) or if the user has been banned, until the token expires naturally.
    *   **Affected Component:** `src/middleware/jwt_auth.py`, `src/index.py`
*   **Threat:** **Hardcoded Default Admin Credentials**
    *   **Severity:** Critical
    *   **Description:** The default admin password is hardcoded in `src/services/auth_service.py`.
    *   **Impact:** If not changed immediately, attackers with knowledge of the codebase can gain full administrative access.
    *   **Affected Component:** `src/services/auth_service.py`

### 3.2 Tampering (Data Integrity)
*   **Threat:** **Unverified Admin Privileges**
    *   **Severity:** High
    *   **Description:** The `is_admin_user` function relies on claims embedded in the JWT (`roles`). Since the token state is not verified against the database on every request, a user whose admin privileges were revoked can still perform admin actions until the token expires.
    *   **Impact:** Unauthorized modification of system state (e.g., System Reset).
    *   **Affected Component:** `src/index.py`

### 3.3 Repudiation
*   **Threat:** **Insufficient User Attribution in Logs**
    *   **Severity:** Medium
    *   **Description:** The `LoggingMiddleware` logs the request path and method but does not extract and log the `user_id` or `username` of the authenticated user.
    *   **Impact:** It is difficult to attribute malicious actions (like deleting a package) to a specific user account using only the application logs.
    *   **Affected Component:** `src/index.py`

### 3.4 Information Disclosure
*   **Threat:** **Token Leakage in Logs**
    *   **Severity:** Critical
    *   **Description:** The `LoggingMiddleware` logs all request headers, including the `Authorization` header which contains the valid Bearer token.
    *   **Impact:** Authentication tokens are exposed in logs, which may be accessible to developers or attackers who gain access to log files.
    *   **Affected Component:** `src/index.py` (Line 145)
*   **Threat:** **Detailed Error Messages**
    *   **Severity:** Low
    *   **Description:** While the system attempts to hide errors in production, misconfiguration of the `ENVIRONMENT` variable could expose stack traces to end-users.
    *   **Affected Component:** `src/index.py`

### 3.5 Denial of Service (DoS)
*   **Threat:** **Regular Expression Denial of Service (ReDoS)**
    *   **Severity:** High
    *   **Description:** The `/artifact/byRegEx` endpoint accepts a user-supplied regex pattern and compiles it using the standard Python `re` module.
    *   **Impact:** An attacker can supply a "catastrophic backtracking" regex (e.g., `(a+)+$`) that causes the server process to hang, consuming 100% CPU.
    *   **Affected Component:** `src/index.py`
*   **Threat:** **Memory Exhaustion via File Uploads**
    *   **Severity:** High
    *   **Description:** The `/upload` endpoint reads the entire uploaded file content into memory (`file.file.read()`) before processing.
    *   **Impact:** Uploading a very large file can cause the application to run out of memory (OOM) and crash.
    *   **Affected Component:** `src/routes/frontend.py`

### 3.6 Elevation of Privilege
*   **Threat:** **Default Admin Account Creation**
    *   **Severity:** Medium
    *   **Description:** The system automatically creates a default admin account if one does not exist.
    *   **Impact:** If the system is deployed without immediately changing the default password, it leaves a persistent backdoor.
    *   **Affected Component:** `src/services/auth_service.py`

## 4. Recommendations & Remediation Plan

| ID | Recommendation | Priority | Effort |
| :--- | :--- | :--- | :--- |
| **REC-01** | **Redact Sensitive Headers in Logs:** Modify `LoggingMiddleware` to remove `Authorization` and `Cookie` headers before logging. | **Critical** | Low |
| **REC-02** | **Enforce Token State Validation:** Update `require_auth` to check the DynamoDB `tokens` table for revocation and usage limits. | **High** | Medium |
| **REC-03** | **Implement Streaming Uploads:** Refactor the `/upload` endpoint to stream data to S3/Disk instead of loading it into RAM. | **High** | Medium |
| **REC-04** | **Mitigate ReDoS:** Use `google-re2` for regex matching or enforce strict timeouts and length limits on regex inputs. | **High** | Medium |
| **REC-05** | **Secure Default Credentials:** Remove hardcoded passwords. Generate a random password on startup if the admin account is created, and log it (securely) or store it in Secrets Manager. | **Medium** | Low |
| **REC-06** | **Improve Audit Logging:** Update middleware to log `user_id` for authenticated requests to ensure non-repudiation. | **Medium** | Low |

