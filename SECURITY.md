# Security Operations Guide

This document captures the current security posture for the CS_450_Phase_2
project: how authentication secrets are handled, how the application falls back
during development, what to do during incidents, and where to find the output
from the automated scans.

## Authentication & Secrets

- The application authenticates graders through `/authenticate` and `/login`. JWT
  middleware is enabled when `ENABLE_AUTH=true` or `JWT_SECRET` is set. When enabled,
  auth checks run before each protected request.
- CORS is configured via the `ALLOWED_ORIGINS` environment variable (comma-separated list
  of origins). Defaults to localhost variants for development. Set this in production
  to allow your frontend domains (e.g., `ALLOWED_ORIGINS=https://app.example.com,https://www.example.com`).
- Basic rate limiting is enforced globally via `RateLimitMiddleware` (default:
  120 requests per 60 seconds per client IP). Adjust with environment variables:
  `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`, or disable with
  `DISABLE_RATE_LIMIT=true` for trusted environments only.
- Environment guardrails:
  - `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` are validated on startup.
    Invalid or non-positive values trigger a warning and fall back to the defaults,
    preventing crashes from misconfigured environment variables.
  - Upper bounds are enforced: `RATE_LIMIT_REQUESTS` is capped at 10000 and
    `RATE_LIMIT_WINDOW_SECONDS` is capped at 3600 seconds (1 hour) to prevent
    misconfiguration that could cause memory issues. Values exceeding these limits
    trigger warnings and fall back to defaults.
- Authorization parsing is centralized in `src/utils/auth.py`, ensuring all
  components (middleware and legacy endpoints) interpret bearer tokens
  consistently and apply identical validation rules.
- Admin/grader passwords are sourced from AWS Secrets Manager when
  `AUTH_ADMIN_SECRET_NAME` is set and the runtime IAM role has
  `secretsmanager:GetSecretValue`.
  - Acceptable secret payloads:
    - List: `["NewAdminPassword123!"]`
    - Object: `{"passwords": ["NewAdminPassword123!"]}`
  - Password validation: The system validates that all password entries are
    non-empty strings before caching. The password normalization logic no longer
    strips trailing semicolons, ensuring appended characters cannot match default
    credentials.
- Development fallback:
  - If `AUTH_ADMIN_SECRET_NAME` is not provided in non-production environments,
    the code logs the failure and falls back to the built-in `DEFAULT_PASSWORDS`.
    This keeps local environments functional.
- Production:
  - If `AUTH_ADMIN_SECRET_NAME` is not set in production (`ENVIRONMENT=production`),
    the system logs at **error** level and raises a `ValueError`, preventing startup
    with default credentials.
  - Any unexpected error retrieving the secret (ClientError, parsing failures, etc.)
    logs at **error** level and re-raises when `ENVIRONMENT=production`, preventing
    silent fallback to default credentials. Monitor CloudWatch for the corresponding
    error log and remediate IAM or Secrets Manager issues immediately.
  - Password cache initialization is thread-safe using a lock to prevent redundant
    Secrets Manager calls under concurrent load.

### Required Environment Variables

| Variable                    | Description                                                                          |
| --------------------------- | ------------------------------------------------------------------------------------ |
| `AUTH_ADMIN_SECRET_NAME`    | Secret name or full ARN of the admin password list. Required in production.          |
| `AWS_REGION`                | Region hosting the secret. Defaults to `us-east-1` if omitted.                       |
| `ENABLE_AUTH`               | Set to `"true"` to enable JWT authentication middleware.                             |
| `JWT_SECRET`                | Alternative to `ENABLE_AUTH`: if set, enables JWT authentication.                    |
| `ENVIRONMENT`               | Set to `"production"` to enforce strict secret validation.                           |
| `RATE_LIMIT_REQUESTS`       | Maximum requests per window (default: 120, max: 10000).                              |
| `RATE_LIMIT_WINDOW_SECONDS` | Time window in seconds (default: 60, max: 3600).                                     |
| `DISABLE_RATE_LIMIT`        | Set to `"true"` to disable rate limiting (trusted environments only).                |
| `ALLOWED_ORIGINS`           | Comma-separated list of CORS allowed origins. Defaults to localhost for development. |

### Secret Rotation Procedure

1. Provision a new secret value (list or dict) in Secrets Manager.
2. Update `AUTH_ADMIN_SECRET_NAME` (or rotate the value in-place with
   `PutSecretValue`).
3. Redeploy the service to pick up the new secret.
4. Invalidate any outstanding tokens (e.g. call `/reset` or purge the tokens
   table) so old credentials cannot be reused.

### Incident Response Checklist

1. **Suspected credential leak**:
   - Rotate the secret immediately (steps above).
   - Purge/rotate active JWT tokens (`/reset` clears the registry and token
     cache).
   - Redeploy with the new secret.
2. **Secrets Manager outage / permission problems**:
   - Check CloudWatch logs for error messages related to secret retrieval.
   - In production, the application will fail to start if `AUTH_ADMIN_SECRET_NAME` is
     not set, preventing use of default credentials.
   - Verify IAM role has `secretsmanager:GetSecretValue`.
   - Validate that `AUTH_ADMIN_SECRET_NAME` and `AWS_REGION` are set correctly.
   - Check that the secret payload structure matches expected formats (list or object
     with `passwords` key).

## IAM Policy Implementation

The repository implements a least-privilege IAM policy architecture using Terraform,
with service-specific policies scoped to the minimum required permissions. All policies
are defined in the `infra/` directory and follow a modular structure.

### Policy Organization

IAM policies are organized by service and environment:

- **`infra/envs/dev/iam_role.tf`**: Defines ECS task roles with trust relationships
  allowing `ecs-tasks.amazonaws.com` to assume the roles.
- **`infra/envs/dev/iam_api.tf`**: API service task role policies (read/write access
  to S3 and DynamoDB).
- **`infra/envs/dev/iam_validator.tf`**: Validator service task role policies (read-only
  S3, read/update DynamoDB, Secrets Manager access).
- **`infra/modules/iam/main.tf`**: Legacy shared policy for team members (`group106_project_policy`).

### API Service Policies

The API service (`api-task-role-dev`) receives three scoped policies:

1. **DynamoDB Read/Write** (`api-ddb-rw-dev`):
   - Read: `GetItem`, `BatchGetItem`, `Query`, `Scan`, `DescribeTable`
   - Write: `PutItem`, `UpdateItem`, `DeleteItem`, `BatchWriteItem`
   - Resources: `packages` table and its indexes only

2. **S3 Packages Read/Write** (`api-s3-packages-rw-dev`):
   - List: `ListBucket` with prefix condition `packages/*`
   - Read/Write: `GetObject`, `PutObject`, `DeleteObject`, `AbortMultipartUpload`,
     `ListMultipartUploadParts` on `pkg-artifacts/packages/*`
   - Condition: Requires `s3:x-amz-server-side-encryption = aws:kms`

3. **KMS for S3** (`api-kms-s3-dev`):
   - Actions: `Encrypt`, `Decrypt`, `ReEncrypt*`, `GenerateDataKey*`, `DescribeKey`
   - Condition: `kms:ViaService = s3.us-east-1.amazonaws.com`
   - Resource: S3 KMS key ARN only

### Validator Service Policies

The Validator service (`validator-task-role-dev`) receives four scoped policies:

1. **DynamoDB Minimal Read/Update** (`validator-ddb-min-rw`):
   - Read: `GetItem`, `BatchGetItem`, `Query`, `Scan`, `DescribeTable`
   - Update: `UpdateItem` only (for status/metrics fields)
   - Resources: `packages` table and indexes

2. **S3 Inputs Read-Only** (`validator-s3-inputs-ro`):
   - List: `ListBucket` with prefix condition `validator/inputs/*`
   - Read: `GetObject`, `GetObjectTagging` on `pkg-artifacts/validator/inputs/*`

3. **KMS for S3 (Decrypt-Only)** (`validator-kms-s3-ro`):
   - Actions: `Decrypt`, `DescribeKey`, `GenerateDataKey*`
   - Condition: `kms:ViaService = s3.us-east-1.amazonaws.com`

4. **Secrets Manager for JWT** (`validator-secrets-jwt-ro`):
   - Actions: `GetSecretValue`, `DescribeSecret` on JWT secret ARN
   - KMS: `Decrypt`, `DescribeKey`, `GenerateDataKey*` via Secrets Manager service
   - Condition: `kms:ViaService = secretsmanager.us-east-1.amazonaws.com`

**Note**: The API service does not currently have a Secrets Manager policy for admin
passwords. If `AUTH_ADMIN_SECRET_NAME` is used, the API service's ECS task role must be
granted `secretsmanager:GetSecretValue` on the admin secret ARN. This should be added to
`infra/envs/dev/iam_api.tf` following the same pattern as the validator's JWT secret policy.

### Team Member Policies

The `group106_project_policy` (defined in `infra/modules/iam/main.tf`) provides team
members with:

- **S3**: `PutObject`, `GetObject`, `ListBucket`, and multipart upload operations on
  `pkg-artifacts/packages/*` and `pkg-artifacts/validators/*`
- **DynamoDB**: `PutItem`, `GetItem`, `UpdateItem`, `Query` on project tables
- **No access** to: Lambda, API Gateway, CloudWatch, ECS, or other AWS services

**Rationale for Restricted Access**: Team members are intentionally restricted from
infrastructure services (Lambda, API Gateway, CloudWatch, ECS, etc.) for the following
security and operational reasons:

1. **Infrastructure as Code (IaC)**: All infrastructure changes should be made through
   Terraform in version control, not via manual console access. This ensures:
   - Changes are reviewed through pull requests
   - Infrastructure state is tracked and reproducible
   - Rollbacks are possible through version control
   - Changes are documented in commit history

2. **Separation of Concerns**: Team members need to work with application data (artifacts,
   packages, user data) but don't need to modify the underlying infrastructure. This
   separation prevents:
   - Accidental service disruptions (e.g., deleting API Gateway stages, modifying
     Lambda functions)
   - Unauthorized infrastructure changes that could affect other team members
   - Production outages from misconfigured services

3. **Least Privilege Principle**: Team members receive only the minimum permissions
   required for their development and testing tasks. Access to infrastructure services
   would grant unnecessary privileges that could be misused or accidentally cause harm.

4. **Audit and Compliance**: Infrastructure changes should be traceable through Terraform
   state and Git history. Manual console changes bypass these audit trails and make it
   difficult to track who made what changes and when.

5. **Production Safety**: Restricting infrastructure access prevents team members from
   accidentally or maliciously modifying production services, scaling configurations,
   or security settings that could impact system availability or security posture.

Infrastructure management remains the responsibility of administrators who have
appropriate access and use Terraform to make controlled, auditable changes.

## Validator Timeout Implementation

The validator service executes customer-provided Python scripts stored in S3 to validate
package access. To prevent denial-of-service (DoS) attacks via infinite loops or
long-running scripts, the system implements multiple layers of timeout protection.

### Problem Statement

Without timeout enforcement, a malicious validator script could:

- Loop indefinitely, consuming CPU and blocking ECS tasks
- Exhaust system resources, preventing other validators from running
- Cause service unavailability by saturating task capacity

**Root Cause Identified**: ECS Fargate does not automatically kill containers based on
wall-clock time; it only terminates tasks when CPU or memory quotas are exceeded. A
validator script could run indefinitely within resource limits, blocking the task.

### Application-Level Timeout

The primary timeout mechanism is implemented in `src/services/validator_service.py`:

1. **Subprocess Isolation**: Validator scripts execute in a separate process using
   Python's `multiprocessing` module with the `spawn` context, providing process-level
   isolation.

2. **Configurable Timeout**: The timeout duration is controlled via the
   `VALIDATOR_TIMEOUT_SEC` environment variable (default: `5` seconds).

3. **Timeout Enforcement**:
   - The main process spawns a child process to execute the validator script
   - The main process calls `process.join(timeout)` to wait for completion
   - If the process is still alive after the timeout, it is terminated via
     `process.terminate()` and `process.join()` to ensure cleanup

4. **Error Response**: On timeout, the API returns:

   ```json
   {
     "valid": false,
     "error": "Validator execution timed out after {timeout} seconds"
   }
   ```

5. **Monitoring**: Each timeout event:
   - Logs an error message at ERROR level
   - Publishes a CloudWatch metric `validator.timeout.count` (namespace configurable
     via `VALIDATOR_METRIC_NAMESPACE`, default: `ValidatorService`)
   - Logs the download event to DynamoDB with status `blocked` and the timeout reason

### Infrastructure-Level Timeouts

Additional timeout protection exists at the infrastructure layer:

1. **ECS Container Health Check** (`infra/modules/ecs/main.tf`):
   - Timeout: `5` seconds
   - Interval: `30` seconds
   - Start period: `60` seconds
   - Unhealthy containers are replaced automatically

2. **Application Load Balancer Health Check** (`infra/modules/ecs/main.tf`):
   - Timeout: `5` seconds
   - Interval: `30` seconds
   - Unhealthy targets are removed from the target group

3. **ECS Task Resource Limits**:
   - Memory: `2048 MB` (hard limit)
   - CPU: `1024` units
   - Tasks exceeding these limits are terminated by ECS

### Configuration

| Environment Variable            | Default                   | Description                                  |
| ------------------------------- | ------------------------- | -------------------------------------------- |
| `VALIDATOR_TIMEOUT_SEC`         | `5`                       | Maximum execution time for validator scripts |
| `VALIDATOR_METRIC_NAMESPACE`    | `ValidatorService`        | CloudWatch namespace for metrics             |
| `VALIDATOR_TIMEOUT_METRIC_NAME` | `validator.timeout.count` | Metric name for timeout events               |

### Testing and Validation

The timeout mechanism is covered by comprehensive unit tests in
`tests/unit/test_validator_timeout.py`:

- **Success path**: Validator completes within timeout
- **Timeout path**: Infinite loop triggers timeout, metric published, error returned
- **Error handling**: Syntax errors, missing functions, exceptions are properly handled
- **No false positives**: Successful validators do not trigger timeout metrics

### Security Benefits

1. **DoS Prevention**: Prevents malicious scripts from consuming resources indefinitely
2. **Resource Protection**: Ensures validator tasks remain available for legitimate requests
3. **Observability**: CloudWatch metrics enable alerting on timeout patterns
4. **Fail-Safe Design**: Timeouts default to a conservative 5 seconds, preventing
   resource exhaustion even if misconfigured

### Operational Considerations

- **Adjusting Timeout**: Increase `VALIDATOR_TIMEOUT_SEC` if legitimate validators
  require more time, but monitor CloudWatch metrics to ensure timeouts remain rare
- **Alerting**: Set up CloudWatch alarms on `validator.timeout.count` to detect
  potential DoS attempts or performance degradation
- **Logging**: Review timeout logs in CloudWatch Logs (`/ecs/validator-service`) to
  identify patterns or problematic validator scripts

### Policy Validation

The repository includes automated IAM policy validation via Terratest in `tests/terraform/`:

- **Test**: `iam_policies_test.go` validates that no Terraform-managed IAM policy
  includes `Action="*"` or `Resource="*"`
- **Execution**: Run `cd tests/terraform && go test ./...` to validate policies
- **Purpose**: Ensures all policies follow least-privilege principles with explicit
  actions and resources

### Security Principles

1. **Least Privilege**: Each service receives only the minimum permissions required for
   its function.
2. **Resource Scoping**: All policies target specific ARNs (tables, buckets, keys) rather
   than wildcards.
3. **Condition-Based Access**: S3 and KMS policies use service conditions
   (`kms:ViaService`) to restrict usage to specific AWS services.
4. **Prefix Restrictions**: S3 list operations are limited to specific prefixes
   (`packages/*`, `validator/inputs/*`).
5. **Encryption Enforcement**: S3 write operations require KMS encryption via conditions.

### Policy Maintenance

When adding new services or permissions:

1. Create a new policy document in the appropriate `iam_*.tf` file
2. Attach the policy to the relevant task role using `aws_iam_role_policy_attachment`
3. Run the Terratest validation to ensure no wildcards are introduced
4. Update this documentation section to reflect the new permissions

## CI/CD Security Scans

The workflow `.github/workflows/ci.yml` runs on push, pull request, manual
dispatch. It contains four jobs:

1. **Unit Tests (`test`)** – sanity check via `./run install && ./run test`.
2. **CodeQL (`codeql`)** – static analysis uploaded to the repository
   _Security_ tab (Code scanning alerts).
3. **Dependency Security (`dependency-security`)**:
   - Installs pinned `pip-audit` and `cyclonedx-bom`.
   - Generates `pip-audit-report.json` and `sbom.json` artifacts.
   - Installs `jq` and fails the job if pip-audit finds **High** (or higher)
     vulnerabilities.
4. **Trivy Scan (`trivy-scan`)**:
   - Caches the vulnerability DB.
   - Produces `trivy-results.sarif` (filesystem scan ignoring unfixed CVEs).
   - Uploads SARIF to GitHub’s Security tab and as a downloadable artifact.
   - Installs `jq` and fails the job when any High/Critical items are present.

### Where to Find Reports

- **Artifacts**: Each workflow run exposes downloadable artifacts in the
  _Actions_ tab (`security-reports`, `trivy-results`).
- **Security tab**: Both CodeQL and Trivy SARIF uploads appear under _Security →
  Code scanning alerts_ for long-term tracking.
- **Manual scans**: The latest OWASP ZAP report is checked in at
  `docs/security/owasp-zap-report.html` for offline review.

### Outstanding Actions

- Security headers (`Strict-Transport-Security`, `X-Content-Type-Options`,
  `Cache-Control`) are not currently implemented in the application code. Consider
  adding a middleware to inject these headers for enhanced security posture.

### Error Handling Practices

- Application logs (CloudWatch or local stdout) receive full stack traces via
  `logger.error(..., exc_info=True)`, but user-facing `HTTPException` payloads
  avoid embedding raw exception messages to reduce information disclosure.
- When adding new endpoints, follow the same pattern: log the detailed error,
  return a generic, user-friendly explanation to the caller.
