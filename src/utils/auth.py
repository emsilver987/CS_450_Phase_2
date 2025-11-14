from __future__ import annotations

from typing import Mapping

from fastapi import HTTPException


def get_authorization_header(headers: Mapping[str, str]) -> str | None:
    """
    Return the first available authorization header value.

    Favors standard ``Authorization`` header but falls back to legacy
    ``X-Authorization`` if present. Returns ``None`` when neither is supplied.
    """
    if headers is None:
        return None
    return headers.get("authorization") or headers.get("Authorization") or headers.get(
        "x-authorization"
    )


def parse_authorization_token(header_value: str | None) -> str:
    """
    Normalize and extract the token value from a header string.

    Accepts both ``Bearer <token>`` and raw token formats to preserve backwards
    compatibility with legacy clients.

    Raises:
        ValueError: When the header is missing or the token component is empty.
    """
    if not header_value:
        raise ValueError("Authorization header missing")

    raw = header_value.strip()
    if not raw:
        raise ValueError("Authorization header empty")

    if raw.lower().startswith("bearer "):
        token = raw.split(" ", 1)[1].strip()
    else:
        token = raw

    if not token:
        raise ValueError("Authorization token missing")

    return token


def extract_token_or_401(headers: Mapping[str, str]) -> str:
    """
    Convenience wrapper that raises ``HTTPException(401)`` on parsing failure.

    Includes WWW-Authenticate header per RFC 7235.
    """
    try:
        header_value = get_authorization_header(headers)
        return parse_authorization_token(header_value)
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

