"""
Shared fixtures and utilities for index endpoint tests
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Mock boto3 and watchtower to prevent startup hangs and logging errors
_boto3_patcher = patch("boto3.client")
_boto3_patcher.start()
from src.index import app

client = TestClient(app)

# Test constants
TEST_MODEL_ID = "test-id"
TEST_MODEL_NAME = "test-model"
TEST_DATASET_ID = "test-dataset-id"
TEST_DATASET_NAME = "test-dataset"
TEST_CODE_ID = "test-code-id"
TEST_CODE_NAME = "test-code"
RATING_STATUS_PENDING = "pending"
RATING_STATUS_COMPLETED = "completed"
RATING_STATUS_FAILED = "failed"
RATING_STATUS_DISQUALIFIED = "disqualified"


@pytest.fixture(scope="session", autouse=True)
def cleanup_boto3_patch():
    """Cleanup boto3 patch at end of session"""
    yield
    try:
        if _boto3_patcher:
            _boto3_patcher.stop()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
def mock_auth():
    with patch("src.index.verify_auth_token") as mock:
        mock.return_value = True
        yield mock


@pytest.fixture
def mock_s3_service():
    with patch("src.index.list_models") as mock_list:
        with patch("src.index.list_artifacts_from_s3") as mock_list_s3:
            yield {"list_models": mock_list, "list_artifacts_from_s3": mock_list_s3}


@pytest.fixture
def mock_artifact_storage():
    with patch("src.index.list_all_artifacts") as mock_list:
        with patch("src.index._artifact_storage", {}) as mock_storage:
            yield {"list_all_artifacts": mock_list, "storage": mock_storage}


@pytest.fixture(autouse=True)
def reset_rating_state():
    """Reset rating state between tests to ensure test isolation."""
    from src.index import (
        _rating_status,
        _rating_locks,
        _rating_results,
        _rating_start_times
    )
    
    # Store original state
    original_status = _rating_status.copy()
    original_locks = _rating_locks.copy()
    original_results = _rating_results.copy()
    original_start_times = _rating_start_times.copy()
    
    # Clear state before test
    _rating_status.clear()
    _rating_locks.clear()
    _rating_results.clear()
    _rating_start_times.clear()
    
    yield
    
    # Restore original state after test
    _rating_status.clear()
    _rating_status.update(original_status)
    _rating_locks.clear()
    _rating_locks.update(original_locks)
    _rating_results.clear()
    _rating_results.update(original_results)
    _rating_start_times.clear()
    _rating_start_times.update(original_start_times)

