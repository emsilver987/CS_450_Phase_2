# Changelog

## Unreleased

- Improved`RateLimitMiddleware` cleanup to prevent unbounded memory growth by pruning stale client entries and purging empty per-client structures.
- Improved rate-limiter concurrency by introducing per-client `asyncio.Lock` instances while keeping a lightweight global gate for cleanup.
- Added production safeguards for admin-secret retrieval: all AWS Secrets Manager errors (including missing secret name, ClientError, parsing failures) now fail fast in production instead of falling back to default passwords, preventing attackers from forcing use of well-known credentials.
- Made `_load_expected_passwords` initialization thread-safe with a lock to prevent redundant Secrets Manager calls under concurrent load.
- Tightened password normalization by removing the legacy semicolon-stripping fallback, ensuring appended characters cannot match default credentials.
- Hardened Secrets Manager parsing: validate password payload structure and enforce non-empty string entries before caching admin credentials.
- Centralized authorization header parsing in `src/utils/auth.py`, removing duplicated logic between `src/index.py` and `src/middleware/jwt_auth.py`.
- Introduced a unit test (`tests/unit/test_auth_public.py::test_load_expected_passwords_raises_in_production`) that verifies production raises on secret load failures.
- Documented testing prerequisites in `docs/tests.md`, covering virtualenv setup and dependency installation to avoid `No module named pytest`.
- Validated rate-limit environment variables in `src/entrypoint.py`; invalid values fall back to defaults with warnings, and middleware registration is explicit.
- Reordered middleware in `src/entrypoint.py` so rate limiting executes before authentication (rate limiting added last, runs first in LIFO order), preventing brute-force attacks from bypassing rate limits. Added `DISABLE_RATE_LIMIT` environment variable support.
- Updated `SECURITY.md` to reflect the strengthened secret-handling and rate-limit configuration safeguards.
- Standardized artifact error responses in `src/index.py` to use "There are missing fields..." phrasing for consistency and clearer messaging.
- Added `WWW-Authenticate: Bearer` header to all 401 Unauthorized responses across `src/utils/auth.py`, `src/index.py`, and `src/services/auth_service.py` to comply with RFC 7235 and help clients understand the required authentication scheme.
- Made CORS allowed origins configurable via `ALLOWED_ORIGINS` environment variable in `src/index.py`, defaulting to localhost for development. This enables deployment to production without code changes by setting production domains in the environment variable.
- Added `_format_error_detail` helper function in `src/index.py` to conditionally include exception details in error messages: includes `{str(e)}` in development for debugging, but excludes it in production to prevent information disclosure. Updated all artifact-related exception handlers to use this helper.
- Extracted admin authorization logic into `is_admin_user()` helper function in `src/index.py` to eliminate code duplication and ensure consistent admin checks across the codebase. The function checks roles, username, is_admin flag, and sub fields, and uses `DEFAULT_ADMIN_USERNAME` constant from `auth_service` instead of hardcoded values.
