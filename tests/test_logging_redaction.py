import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request
from src.index import LoggingMiddleware

@pytest.mark.asyncio
async def test_logging_middleware_redaction():
    # Mock the app and call_next
    app = MagicMock()
    middleware = LoggingMiddleware(app)
    
    async def call_next(request):
        return MagicMock(status_code=200)

    # Create a mock request with sensitive headers
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [
            (b"authorization", b"Bearer secret_token"),
            (b"cookie", b"session=secret_cookie"),
            (b"user-agent", b"test-agent"),
        ],
    }
    request = Request(scope)

    # Patch logger to capture output
    with patch("src.index.logger") as mock_logger:
        await middleware.dispatch(request, call_next)

        # Check if redaction happened in the logs
        # We expect one of the calls to contain the redacted headers
        found_redacted = False
        for call in mock_logger.info.call_args_list:
            args, _ = call
            log_message = args[0]
            if "Headers:" in log_message:
                # Check that secrets are NOT in the log
                assert "secret_token" not in log_message
                assert "secret_cookie" not in log_message
                # Check that redaction marker IS in the log
                assert "[REDACTED]" in log_message
                found_redacted = True
        
        assert found_redacted, "Did not find a log entry with redacted headers"
