# JWT Authentication Enforcement

## Overview

The API enforces JSON Web Tokens (JWT) for every endpoint that the
`ece461_fall_2025_openapi_spec-2.yaml` specification marks as requiring the
`X-Authorization` header. Enforcement lives in `src/middleware/jwt_auth.py`, so
all protected requests pass through a single verifier before reaching route
handlers.

Key behaviours:

1. **Header Support** – Tokens are accepted from both `Authorization`
   (standard `Bearer <token>` scheme) and the spec’s `X-Authorization` header.
2. **Public Allowlist** – The spec designates `/health`, `/health/components`,
   `/authenticate`, and documentation routes as public. These paths remain
   reachable without credentials via the middleware’s exempt list.
3. **Ephemeral `/authenticate` Tokens** – The `/authenticate` endpoint now
   verifies admin credentials (loaded from AWS Secrets Manager when
   `AUTH_ADMIN_SECRET_NAME` is set) and issues short-lived JWTs by calling
   `auth_service.create_jwt_token`. Responses are JSON
   `{"token": "bearer ...", "token_id": ..., "expires_at": ...}` and every
   issuance is persisted with `store_token`.
4. **JWT Validation** – `verify_jwt_token` decodes HS256 tokens, enforces the
   `exp` claim, and returns `None` on failure. The middleware returns
   `401 {"detail": "Unauthorized"}` for any missing, malformed, or expired token,
   matching the spec’s language.
5. **Request Context** – Successful verifications stash the decoded payload on
   `request.state.auth`, so handlers can use `require_auth(request)` to retrieve
   claims without re-decoding.

## Route-Level Usage

Use `require_auth(request)` (defined in `src/index.py`) inside protected
endpoints. It raises `HTTPException(status_code=401)` if the middleware did not
attach auth data, ensuring consistent enforcement.

```python
@app.post("/artifacts")
async def list_artifacts(request: Request):
    auth = require_auth(request)  # raises 401 if missing/invalid
    ...
```

For role checks, inspect `auth`:

```python
auth = require_auth(request)
if "admin" not in auth.get("roles", []):
    raise HTTPException(status_code=401, detail="You do not have permission …")
```

## Test Coverage

`tests/unit/test_jwt_middleware.py` exercises the middleware without spinning up
a FastAPI app:

- Exempt paths bypass auth.
- Missing headers produce 401.
- Invalid or expired JWTs return 401.
- Valid JWTs, via either `Authorization` or `X-Authorization`, attach payloads to
  `request.state.auth`.

`tests/unit/test_auth_public.py` stubs Secrets Manager to verify that
`/authenticate` issues JWTs on success and rejects bad credentials.

Run the tests with:

```bash
source .venv/bin/activate
pytest tests/unit/test_jwt_middleware.py tests/unit/test_auth_public.py
```

## Maintenance Tips

- Update the exempt path lists if the spec’s public endpoints change.
- Keep `verify_jwt_token` aligned with any new JWT requirements (issuer,
  audience, leeway).
- Secrets Manager: ensure `AUTH_ADMIN_SECRET_NAME` and the execution role permit
  `secretsmanager:GetSecretValue`; otherwise the code falls back to the default
  password set for development compatibility.
