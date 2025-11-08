# Middleware Guidance

This package contains reusable FastAPI middlewares that we can mix into the main application. Two key pieces live here:

1. `errorHandler.py` — Common exception handling logic.
2. `jwt_auth.py` — (legacy) middleware used in earlier iterations for JWT enforcement.

## JWT Auth Middleware (`jwt_auth.py`)

The project now centralizes JWT verification directly in `src/index.py` via the shared `verify_auth_token` helper. That helper:

- Extracts the bearer token from `Authorization` or `X-Authorization`.
- Calls `services.auth_service.verify_jwt_token`.
- Raises `HTTPException(403)` if the token is missing, expired, or invalid.
- Stores the decoded claims on `request.state.auth_claims` for downstream handlers.

Because JWT enforcement is happening in the main app, the legacy `JWTAuthMiddleware` in this folder is kept only as a reference/utility for standalone services. If you need to reuse it:

```python
from fastapi import FastAPI
from src.middleware.jwt_auth import JWTAuthMiddleware

app = FastAPI()
app.add_middleware(
    JWTAuthMiddleware,
    exempt_paths=("/health", "/health/components")
)
```

For the core API, rely on `verify_auth_token` and avoid importing this middleware directly, so we maintain a single source of truth for signature + expiry checks.
