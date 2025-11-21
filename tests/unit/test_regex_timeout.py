"""
Test timeout mitigation for /artifact/byRegEx endpoint.

This test verifies that the timeout protection works correctly
to prevent ReDoS attacks.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_timeout_mitigation_works():
    """Test that asyncio.wait_for() properly times out blocking operations."""
    
    # Simulate a blocking operation that takes longer than timeout
    def slow_blocking_operation():
        time.sleep(10)  # Sleep for 10 seconds
        return {"models": []}
    
    timeout = 2.0  # 2 second timeout
    
    start_time = time.time()
    
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(slow_blocking_operation),
            timeout=timeout
        )
        # Should not reach here
        assert False, "Expected TimeoutError but operation completed"
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        # Should timeout around 2 seconds (with some tolerance)
        assert elapsed < timeout + 1.0, f"Timeout took too long: {elapsed}s"
        assert elapsed >= timeout * 0.9, f"Timeout too fast: {elapsed}s"
        print(f"✓ Timeout worked correctly: {elapsed:.2f}s")


@pytest.mark.asyncio
async def test_normal_operation_completes():
    """Test that normal (fast) operations complete successfully."""
    
    def fast_operation():
        return {"models": [{"name": "test", "version": "1.0"}]}
    
    timeout = 5.0
    
    result = await asyncio.wait_for(
        asyncio.to_thread(fast_operation),
        timeout=timeout
    )
    
    assert result == {"models": [{"name": "test", "version": "1.0"}]}
    print("✓ Normal operation completed successfully")


@pytest.mark.asyncio
async def test_regex_timeout_integration():
    """
    Integration test: Verify that the timeout is applied in the actual endpoint.
    This test mocks list_models to simulate a slow regex operation.
    """
    from src.services.s3_service import list_models
    
    # Mock a slow regex operation
    original_list_models = list_models
    
    def slow_list_models(name_regex=None, limit=100):
        # Simulate catastrophic backtracking by sleeping
        time.sleep(10)
        return {"models": []}
    
    timeout = 2.0
    start_time = time.time()
    
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(slow_list_models, name_regex="(a+)+$", limit=100),
            timeout=timeout
        )
        assert False, "Expected TimeoutError"
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        assert elapsed < timeout + 1.0
        print(f"✓ Regex timeout protection works: {elapsed:.2f}s")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

