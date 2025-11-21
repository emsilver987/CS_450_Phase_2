#!/usr/bin/env python3
"""
Test that SecurityHeadersMiddleware actually adds headers to responses.
This test makes a real HTTP request to verify headers are present.
"""
from __future__ import annotations

# Handle both pytest and direct execution
try:
    import pytest
    pytest.importorskip("httpx")  # FastAPI TestClient requires httpx
except ImportError:
    # If pytest is not available, check httpx directly
    try:
        import httpx  # noqa: F401
    except ImportError:
        raise RuntimeError(
            "httpx is required for this test. Install it with: pip install httpx"
        )

from fastapi.testclient import TestClient


def test_security_headers_in_response():
    """Test that security headers are present in actual HTTP responses."""
    from src.entrypoint import app

    client = TestClient(app)

    # Make a request to any endpoint
    # Using a simple endpoint that should exist
    response = client.get("/health")

    print(f"Status Code: {response.status_code}")
    print("\nResponse Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")

    # Check for security headers
    security_headers = {
        "strict-transport-security": False,
        "x-content-type-options": False,
        "x-frame-options": False,
        "x-xss-protection": False,
        "content-security-policy": False,
        "referrer-policy": False,
        "permissions-policy": False,
    }

    # Convert response headers to lowercase keys for checking
    response_headers_lower = {k.lower(): v for k, v in response.headers.items()}

    print("\nSecurity Headers Check:")
    all_present = True
    for header_name, _ in security_headers.items():
        is_present = header_name in response_headers_lower
        security_headers[header_name] = is_present
        status = "✓" if is_present else "✗"
        value = response_headers_lower.get(header_name, "NOT FOUND")
        print(f"  {status} {header_name}: {value}")
        if not is_present:
            all_present = False

    print(f"\n{'='*60}")
    if all_present:
        print("✅ ALL SECURITY HEADERS PRESENT")
        print("   SecurityHeadersMiddleware is working correctly!")
        assert all_present, "All security headers should be present"
        return True
    else:
        print("❌ SOME SECURITY HEADERS MISSING")
        print("   SecurityHeadersMiddleware may not be working correctly")
        assert False, "Some security headers are missing"
        return False


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("SecurityHeadersMiddleware Runtime Verification")
    print("=" * 60)
    print()

    try:
        result = test_security_headers_in_response()
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

