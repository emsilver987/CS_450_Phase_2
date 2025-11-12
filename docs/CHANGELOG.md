# Changelog

## Unreleased

- Hardened `RateLimitMiddleware` cleanup to prevent unbounded memory growth by pruning stale client entries and purging empty per-client structures.
- Improved rate-limiter concurrency by introducing per-client `asyncio.Lock` instances while keeping a lightweight global gate for cleanup.
- Added production safeguards for admin-secret retrieval: unexpected AWS Secrets Manager errors now log at error level and re-raise when `ENVIRONMENT=production`.
- Introduced a unit test (`tests/unit/test_auth_public.py::test_load_expected_passwords_raises_in_production`) that verifies production raises on secret load failures.
- Documented testing prerequisites in `docs/tests.md`, covering virtualenv setup and dependency installation to avoid `No module named pytest`.
- Validated rate-limit environment variables in `src/entrypoint.py`; invalid values fall back to defaults with warnings, and middleware registration is explicit.
- Updated `SECURITY.md` to reflect the strengthened secret-handling and rate-limit configuration safeguards.
