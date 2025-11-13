# Security Operations Guide

This document captures the current security posture for the CS_450_Phase_2
project: how authentication secrets are handled, how the application falls back
during development, what to do during incidents, and where to find the output
from the automated scans.

## Authentication & Secrets

- The application authenticates graders through `/authenticate` and `/login`. JWT
  middleware is enabled by default (set `DISABLE_AUTH=true` to opt out), so auth
  checks run before each protected request.
- CORS is restricted to trusted localhost origins (`localhost`, `localhost:3000`);
  update `allow_origins` in `src/index.py` if additional frontends need access.
- Basic rate limiting is enforced globally via `RateLimitMiddleware` (default:
  120 requests per 60 seconds per client IP). Adjust with environment variables:
  `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`, or disable with
  `DISABLE_RATE_LIMIT=true` for trusted environments only.
- Environment guardrails:
  - `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS` are validated on startup.
    Invalid or non-positive values trigger a warning and fall back to the defaults,
    preventing crashes from misconfigured environment variables.
- Authorization parsing is centralized in `src/utils/auth.py`, ensuring all
  components (middleware and legacy endpoints) interpret bearer tokens
  consistently and apply identical validation rules.
- Admin/grader passwords are sourced from AWS Secrets Manager when
  `AUTH_ADMIN_SECRET_NAME` is set and the runtime IAM role has
  `secretsmanager:GetSecretValue`.
  - Acceptable secret payloads:
    - List: `["NewAdminPassword123!"]`
    - Object: `{"passwords": ["NewAdminPassword123!"]}`
- Development fallback:
  - If the secret name is not provided or `GetSecretValue` fails in non-production
    environments, the code logs the failure and falls back to the built-in
    `DEFAULT_PASSWORDS`. This keeps local environments functional.
- Production:
  - Any unexpected error retrieving the secret now logs at **error** level and
    re-raises when `ENVIRONMENT=production`, preventing silent fallback to default
    credentials. Monitor CloudWatch for the corresponding error log and remediate
    IAM or Secrets Manager issues immediately.

### Required Environment Variables

| Variable                 | Description                                                    |
| ------------------------ | -------------------------------------------------------------- |
| `AUTH_ADMIN_SECRET_NAME` | Secret name or full ARN of the admin password list.            |
| `AWS_REGION`             | Region hosting the secret. Defaults to `us-east-1` if omitted. |

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
   - Check CloudWatch logs for the warning
     `"Falling back to default admin passwords..."`.
   - Verify IAM role has `secretsmanager:GetSecretValue`.
   - Validate that `AUTH_ADMIN_SECRET_NAME` and `AWS_REGION` are set correctly.

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
  `security/owasp-zap-report.html` for offline review.

### Outstanding Actions

- The application now injects security headers (`Strict-Transport-Security`,
  `X-Content-Type-Options`, `Cache-Control`) in `src/entrypoint.py`, but the
  production deployment at
  `https://1q1x0d7k93.execute-api.us-east-1.amazonaws.com/prod/` still returns
  responses without them. Redeploy the service (or update the upstream gateway)
  and re-run `curl -I` or OWASP ZAP to verify the headers are active.

### Error Handling Practices

- Application logs (CloudWatch or local stdout) receive full stack traces via
  `logger.error(..., exc_info=True)`, but user-facing `HTTPException` payloads
  avoid embedding raw exception messages to reduce information disclosure.
- When adding new endpoints, follow the same pattern: log the detailed error,
  return a generic, user-friendly explanation to the caller.
