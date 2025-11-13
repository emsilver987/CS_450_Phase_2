# Changelog

## Unreleased

- Improved`RateLimitMiddleware` cleanup to prevent unbounded memory growth by pruning stale client entries and purging empty per-client structures.
- Improved rate-limiter concurrency by introducing per-client `asyncio.Lock` instances while keeping a lightweight global gate for cleanup.
- Added production safeguards for admin-secret retrieval: unexpected AWS Secrets Manager errors now log at error level and re-raise when `ENVIRONMENT=production`.
- Made `_load_expected_passwords` initialization thread-safe with a lock to prevent redundant Secrets Manager calls under concurrent load.
- Tightened password normalization by removing the legacy semicolon-stripping fallback, ensuring appended characters cannot match default credentials.
- Hardened Secrets Manager parsing: validate password payload structure and enforce non-empty string entries before caching admin credentials.
- Centralized authorization header parsing in `src/utils/auth.py`, removing duplicated logic between `src/index.py` and `src/middleware/jwt_auth.py`.
- Introduced a unit test (`tests/unit/test_auth_public.py::test_load_expected_passwords_raises_in_production`) that verifies production raises on secret load failures.
- Documented testing prerequisites in `docs/tests.md`, covering virtualenv setup and dependency installation to avoid `No module named pytest`.
- Validated rate-limit environment variables in `src/entrypoint.py`; invalid values fall back to defaults with warnings, and middleware registration is explicit.
- Updated `SECURITY.md` to reflect the strengthened secret-handling and rate-limit configuration safeguards.
