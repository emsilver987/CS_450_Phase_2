import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request
from src.index import LoggingMiddleware

@pytest.mark.asyncio
async def test_logging_middleware_audit():
    # Mock app
    app = MagicMock()
    middleware = LoggingMiddleware(app)
    
    # Mock call_next to simulate request processing and auth
    async def call_next(request):
        # Simulate successful auth setting user state
        request.state.user = {"user_id": "audit-user-123", "username": "audit_tester"}
        return MagicMock(status_code=200)

    # Create request
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/audit-test",
        "headers": [],
    }
    request = Request(scope)

    # Patch logger to verify output
    with patch("src.index.logger") as mock_logger:
        await middleware.dispatch(request, call_next)

        # Verify log contains user info
        found_audit_log = False
        for call in mock_logger.info.call_args_list:
            args, _ = call
            log_message = args[0]
            if "User(id=audit-user-123, username=audit_tester)" in log_message:
                found_audit_log = True
                break
        
        assert found_audit_log, "Audit log with user ID not found"

@pytest.mark.asyncio
async def test_logging_middleware_anonymous():
    # Mock app
    app = MagicMock()
    middleware = LoggingMiddleware(app)
    
    async def call_next(request):
        # No user state set (anonymous)
        return MagicMock(status_code=200)

    request = Request({"type": "http", "method": "GET", "path": "/anon", "headers": []})

    with patch("src.index.logger") as mock_logger:
        await middleware.dispatch(request, call_next)

        # Verify log indicates Anonymous
        found_anon_log = False
        for call in mock_logger.info.call_args_list:
            args, _ = call
            log_message = args[0]
            if "Anonymous" in log_message:
                found_anon_log = True
                break
        
        assert found_anon_log, "Anonymous log not found"
