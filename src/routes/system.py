from __future__ import annotations

from fastapi import APIRouter

from src.services.auth_service import ensure_default_admin, purge_tokens

router = APIRouter()

# In-memory database shared with artifacts routes
_INMEM_DB = {"artifacts": []}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/llm-status")
def llm_status():
    """Check if LLM service is available and working"""
    try:
        from src.services.llm_service import is_llm_available, PURDUE_GENAI_API_KEY
        
        available = is_llm_available()
        has_key = bool(PURDUE_GENAI_API_KEY)
        key_length = len(PURDUE_GENAI_API_KEY) if PURDUE_GENAI_API_KEY else 0
        
        return {
            "llm_available": available,
            "api_key_configured": has_key,
            "api_key_length": key_length,
            "status": "ready" if available else "not_configured",
            "message": "LLM service is ready" if available else "LLM API key not configured"
        }
    except Exception as e:
        return {
            "llm_available": False,
            "api_key_configured": False,
            "status": "error",
            "error": str(e),
            "message": f"Error checking LLM status: {str(e)}"
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
