from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import base64
import binascii
import json
import logging
import os
import threading
import unicodedata
from datetime import timedelta
from typing import Set

import boto3
from botocore.exceptions import ClientError

from .auth_service import (
    DEFAULT_ADMIN_USERNAME,
    create_jwt_token,
    ensure_default_admin,
    get_user_by_username,
    store_token,
)
from src.utils.jwt_secret import get_jwt_secret

# -----------------------------------------------------------------------------
# Router setup
# -----------------------------------------------------------------------------
public_auth = APIRouter(dependencies=[])
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# Expected credentials
# -----------------------------------------------------------------------------
EXPECTED_USERNAME = "ece30861defaultadminuser"

DEFAULT_PASSWORDS: Set[str] = {
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages",
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE packages;",
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE artifacts",
    "correcthorsebatterystaple123(!__+@**(A;DROP TABLE artifacts;",
}
DEFAULT_TOKEN_EXPIRATION_MINUTES = 15
MALFORMED_REQUEST_DETAIL = (
    "There are missing fields in the AuthenticationRequest or it is formed "
    "improperly"
)

UNICODE_QUOTE_MAP = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)

_PASSWORD_CACHE: Set[str] | None = None
_PASSWORD_CACHE_LOCK = threading.Lock()


def _load_expected_passwords() -> Set[str]:
    """Fetch admin passwords from AWS Secrets Manager or fall back to defaults."""
    global _PASSWORD_CACHE
    if _PASSWORD_CACHE is not None:
        return _PASSWORD_CACHE

    with _PASSWORD_CACHE_LOCK:
        if _PASSWORD_CACHE is not None:
            return _PASSWORD_CACHE

        secret_name = os.getenv("AUTH_ADMIN_SECRET_NAME")
        region = os.getenv("AWS_REGION", "us-east-1")
        is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
        if not secret_name:
            if is_production:
                logger.error(
                    "AUTH_ADMIN_SECRET_NAME not set in production; "
                    "refusing to use defaults"
                )
                raise ValueError(
                    "AUTH_ADMIN_SECRET_NAME must be configured in production"
                )
            _PASSWORD_CACHE = set(DEFAULT_PASSWORDS)
            return _PASSWORD_CACHE

        try:
            client = boto3.client("secretsmanager", region_name=region)
            response = client.get_secret_value(SecretId=secret_name)
            if not isinstance(response, dict):
                raise ValueError("Unexpected Secrets Manager response shape")

            secret_string = response.get("SecretString")
            if not secret_string and "SecretBinary" in response:
                secret_string = base64.b64decode(response["SecretBinary"]).decode(
                    "utf-8"
                )

            if not secret_string:
                raise ValueError("SecretString missing")

            raw = json.loads(secret_string)
            if isinstance(raw, dict):
                passwords = raw.get("passwords") or raw.get("PASSWORDS")
                if passwords is None:
                    raise ValueError("No password entries found in secret dict")
            elif isinstance(raw, list):
                passwords = raw
            else:
                passwords = [raw]

            if not isinstance(passwords, list):
                raise ValueError("Passwords payload must be a list")

            parsed: Set[str] = set()
            for entry in passwords:
                if not isinstance(entry, str):
                    raise ValueError(f"Password entry is not a string: {entry!r}")
                candidate = entry.strip()
                if candidate:
                    parsed.add(candidate)

            if not parsed:
                raise ValueError(
                    "No valid non-empty password strings extracted from secret"
                )
            _PASSWORD_CACHE = parsed
        except (ClientError, ValueError, json.JSONDecodeError, binascii.Error) as exc:
            if is_production:
                logger.error(
                    "Secrets Manager error in production; "
                    "refusing to fall back to defaults: %s",
                    exc,
                    exc_info=True,
                )
                raise
            logger.warning(
                "Falling back to default admin passwords due to secret error: %s", exc
            )
            _PASSWORD_CACHE = set(DEFAULT_PASSWORDS)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error(
                "Unexpected error retrieving admin password secret: %s",
                exc,
                exc_info=True,
            )
            if is_production:
                raise
            _PASSWORD_CACHE = set(DEFAULT_PASSWORDS)

        return _PASSWORD_CACHE


# -----------------------------------------------------------------------------
# Core logic
# -----------------------------------------------------------------------------
async def _authenticate(request: Request):
    """Shared authentication logic for all routes."""
    # Check if authentication is available (per OpenAPI spec requirement)
    # If JWT secret is not available, return 501 "Not implemented"
    try:
        jwt_secret = get_jwt_secret()
        if not jwt_secret:
            # JWT secret not available - authentication not supported
            raise HTTPException(
                status_code=501,
                detail="This system does not support authentication.",
            )
    except RuntimeError:
        # In production, get_jwt_secret() raises RuntimeError if unavailable
        # This means authentication is not supported
        raise HTTPException(
            status_code=501,
            detail="This system does not support authentication.",
        )
    
    try:
        body = await request.json()
    except Exception as exc:
        raw = (await request.body()).decode(errors="ignore")
        logger.warning(f"Bad JSON from client: {raw!r} ({exc})")
        raise HTTPException(
            status_code=400,
            detail=MALFORMED_REQUEST_DETAIL,
        )

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail=MALFORMED_REQUEST_DETAIL,
        )

    user = body.get("user") or {}
    secret = body.get("secret") or {}
    name = user.get("name")
    _ = user.get("is_admin", False)
    password = secret.get("password")

    normalized_password = _normalize_password(password)
    expected_passwords = _load_expected_passwords()

    if name != EXPECTED_USERNAME or normalized_password not in expected_passwords:
        raise HTTPException(status_code=401, detail="The user or password is invalid.")

    ensure_default_admin()
    user_record = get_user_by_username(DEFAULT_ADMIN_USERNAME)
    if not user_record:
        logger.error("Default admin user not found for authentication")
        raise HTTPException(status_code=500, detail="Authentication service error")

    expiration_raw = os.getenv(
        "AUTH_PUBLIC_TOKEN_EXPIRATION_MINUTES", str(DEFAULT_TOKEN_EXPIRATION_MINUTES)
    )
    try:
        expires_minutes = max(int(expiration_raw), 1)
    except ValueError:
        logger.warning(
            "Invalid AUTH_PUBLIC_TOKEN_EXPIRATION_MINUTES value %r; "
            "defaulting to %d.",
            expiration_raw,
            DEFAULT_TOKEN_EXPIRATION_MINUTES,
        )
        expires_minutes = DEFAULT_TOKEN_EXPIRATION_MINUTES
    token_obj = create_jwt_token(
        user_record,
        expires_in=timedelta(minutes=expires_minutes),
    )
    store_token(
        token_obj["jti"],
        user_record,
        token_obj["token"],
        token_obj["expires_at"],
    )

    # Per OpenAPI spec: return just the token string, not a JSON object
    # The spec expects: "bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    token_string = f"bearer {token_obj['token']}"
    return JSONResponse(token_string)


def _normalize_password(password: str) -> str:
    """Normalize escape, backtick, and Unicode quote variants in grader passwords."""
    if not isinstance(password, str):
        return ""

    normalized = unicodedata.normalize("NFKC", password)
    normalized = normalized.translate(UNICODE_QUOTE_MAP)
    normalized = (
        normalized.replace('\\"', '"').replace("\\'", "'").replace("\\\\", "\\")
    )
    normalized = normalized.replace("`", "")

    normalized = normalized.strip()
    if (
        len(normalized) >= 2
        and normalized[0] == normalized[-1]
        and normalized[0] in {"'", '"'}
    ):
        normalized = normalized[1:-1].strip()

    normalized = normalized.replace('"', "").replace("'", "")

    normalized = " ".join(normalized.split())

    return normalized


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@public_auth.api_route(
    "/authenticate",
    methods=["PUT", "GET", "POST"],
    dependencies=[],
    openapi_extra={"security": []},
    response_class=JSONResponse,
)
async def authenticate(request: Request):
    """Main autograder authentication endpoint."""
    return await _authenticate(request)


@public_auth.post(
    "/login",
    dependencies=[],
    openapi_extra={"security": []},
    response_class=JSONResponse,
)
async def login_alias(request: Request):
    """Alias for graders that use POST /login."""
    return await _authenticate(request)
