from __future__ import annotations

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.middleware.security_headers import SecurityHeadersMiddleware


def _build_scope(path: str, headers: dict[str, str] | None = None) -> dict:
    """Construct a minimal ASGI scope for the middleware to consume."""
    raw_headers = []
    if headers:
        raw_headers = [(k.encode(), v.encode()) for k, v in headers.items()]
    return {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": raw_headers,
        "query_string": b"",
        "client": ("127.0.0.1", 8080),
        "server": ("localhost", 8000),
    }


async def _simple_app(scope, receive, send):
    """Minimal ASGI app that returns a JSON response."""
    response = JSONResponse({"message": "ok"})
    await response(scope, receive, send)


@pytest.mark.asyncio
async def test_security_headers_added():
    """Test that all security headers are added to responses."""
    middleware = SecurityHeadersMiddleware(_simple_app)
    scope = _build_scope("/test")
    received_headers = {}

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal received_headers
        if message["type"] == "http.response.start":
            received_headers = dict(message["headers"])

    await middleware(scope, receive, send)

    # Convert headers from bytes to strings for easier checking
    headers = {k.decode(): v.decode() for k, v in received_headers.items()}

    assert "strict-transport-security" in headers
    assert "max-age=31536000" in headers["strict-transport-security"]
    assert "includesubdomains" in headers["strict-transport-security"].lower()

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["x-xss-protection"] == "1; mode=block"
    assert "content-security-policy" in headers
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "permissions-policy" in headers


@pytest.mark.asyncio
async def test_hsts_configuration():
    """Test HSTS configuration options."""
    middleware = SecurityHeadersMiddleware(
        _simple_app,
        hsts_max_age=86400,  # 1 day
        hsts_include_subdomains=False,
        hsts_preload=True,
    )
    scope = _build_scope("/test")
    received_headers = {}

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal received_headers
        if message["type"] == "http.response.start":
            received_headers = dict(message["headers"])

    await middleware(scope, receive, send)

    headers = {k.decode(): v.decode() for k, v in received_headers.items()}
    hsts = headers["strict-transport-security"]

    assert "max-age=86400" in hsts
    assert "includesubdomains" not in hsts.lower()
    assert "preload" in hsts.lower()


@pytest.mark.asyncio
async def test_custom_csp():
    """Test custom Content-Security-Policy."""
    custom_csp = "default-src 'none'; script-src 'self'"
    middleware = SecurityHeadersMiddleware(
        _simple_app, content_security_policy=custom_csp
    )
    scope = _build_scope("/test")
    received_headers = {}

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal received_headers
        if message["type"] == "http.response.start":
            received_headers = dict(message["headers"])

    await middleware(scope, receive, send)

    headers = {k.decode(): v.decode() for k, v in received_headers.items()}
    assert headers["content-security-policy"] == custom_csp


@pytest.mark.asyncio
async def test_custom_referrer_policy():
    """Test custom Referrer-Policy."""
    middleware = SecurityHeadersMiddleware(
        _simple_app, referrer_policy="no-referrer"
    )
    scope = _build_scope("/test")
    received_headers = {}

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal received_headers
        if message["type"] == "http.response.start":
            received_headers = dict(message["headers"])

    await middleware(scope, receive, send)

    headers = {k.decode(): v.decode() for k, v in received_headers.items()}
    assert headers["referrer-policy"] == "no-referrer"


@pytest.mark.asyncio
async def test_custom_permissions_policy():
    """Test custom Permissions-Policy."""
    custom_policy = "geolocation=(self), microphone=()"
    middleware = SecurityHeadersMiddleware(
        _simple_app, permissions_policy=custom_policy
    )
    scope = _build_scope("/test")
    received_headers = {}

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        nonlocal received_headers
        if message["type"] == "http.response.start":
            received_headers = dict(message["headers"])

    await middleware(scope, receive, send)

    headers = {k.decode(): v.decode() for k, v in received_headers.items()}
    assert headers["permissions-policy"] == custom_policy

