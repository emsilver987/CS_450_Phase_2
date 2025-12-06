"""
Test that pytest can collect all tests without import errors
"""
import pytest
import subprocess
import sys
from pathlib import Path


def test_pytest_collection():
    """Verify pytest can collect tests without errors"""
    project_root = Path(__file__).parent.parent.parent
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=30
    )
    
    # Should not have collection errors
    assert "ERROR collecting" not in result.stderr, (
        f"Collection errors found: {result.stderr}"
    )
    assert "errors during collection" not in result.stderr, (
        f"Collection errors found: {result.stderr}"
    )
    assert result.returncode == 0, (
        f"Collection failed with return code {result.returncode}. "
        f"stderr: {result.stderr}, stdout: {result.stdout}"
    )


def test_unit_tests_collectible():
    """Verify unit tests can be collected in isolation"""
    project_root = Path(__file__).parent.parent.parent
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "tests/unit"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
        timeout=30
    )
    
    # Should not have collection errors
    assert "ERROR collecting" not in result.stderr, (
        f"Unit test collection errors: {result.stderr}"
    )
    assert result.returncode == 0, (
        f"Unit test collection failed. stderr: {result.stderr}, stdout: {result.stdout}"
    )
    # Should have collected at least some tests
    assert "collected" in result.stdout.lower() or "test session starts" in result.stdout.lower(), (
        "No collection output found"
    )

