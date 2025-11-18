from __future__ import annotations

from fastapi import APIRouter

from src.services.auth_service import ensure_default_admin, purge_tokens
from src.utils.jwt_secret import get_jwt_secret_status

router = APIRouter()

# In-memory database shared with artifacts routes
_INMEM_DB = {"artifacts": []}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/secret")
def health_secret():
    """
    Diagnostic endpoint to check JWT secret status.
    Returns information about secret availability without exposing the secret value.
    """
    status = get_jwt_secret_status()
    return {
        "status": "ok" if status["available"] else "error",
        "jwt_secret": status,
    }


@router.get("/tracks")
def tracks():
    return {"tracks": ["access-control", "reproducibility", "reviewedness", "security"]}


@router.post("/reset")
def reset():
    _INMEM_DB["artifacts"].clear()
    purge_tokens()
    ensure_default_admin()
    return {"status": "ok"}


@router.delete("/reset")  # Add this to match spec
def reset_delete():
    _INMEM_DB["artifacts"].clear()
    purge_tokens()
    ensure_default_admin()
    return {"status": "ok"}
