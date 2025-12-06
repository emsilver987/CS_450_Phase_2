"""
Test CI environment requirements
"""
import pytest
import os
import shutil
from pathlib import Path

from tests.utils.chromedriver import find_chromedriver_path, get_chromedriver_install_instruction


def test_chromedriver_available_in_ci():
    """Verify chromedriver is available in CI environment"""
    if os.getenv("CI") != "true":
        pytest.skip("Not running in CI environment")
    
    chromedriver_path = find_chromedriver_path()
    install_cmd = get_chromedriver_install_instruction()
    
    assert chromedriver_path is not None, (
        f"chromedriver not found in CI environment. "
        f"Install with: {install_cmd}"
    )
    assert os.path.exists(chromedriver_path), (
        f"chromedriver path {chromedriver_path} does not exist"
    )


def test_chromium_browser_available_in_ci():
    """Verify chromium-browser is available in CI environment"""
    if os.getenv("CI") != "true":
        pytest.skip("Not running in CI environment")
    
    # Check common CI paths
    chromium_paths = [
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    
    chromium_found = False
    for path in chromium_paths:
        if os.path.exists(path):
            chromium_found = True
            break
    
    # Also check PATH
    if not chromium_found:
        chromium_found = shutil.which("chromium-browser") is not None or \
                        shutil.which("chromium") is not None
    
    assert chromium_found, (
        "chromium-browser not found in CI environment. "
        "Install with: sudo apt-get install chromium-browser"
    )


def test_health_endpoint_exists():
    """Verify health endpoint is accessible"""
    # This test verifies the health endpoint exists in the codebase
    # It doesn't require a running server, just checks the code structure
    
    index_file = Path(__file__).parent.parent.parent / "src" / "index.py"
    system_file = Path(__file__).parent.parent.parent / "src" / "routes" / "system.py"
    
    health_found = False
    
    # Check index.py
    if index_file.exists():
        content = index_file.read_text()
        if '@app.get("/health")' in content or '"/health"' in content:
            health_found = True
    
    # Check system.py
    if not health_found and system_file.exists():
        content = system_file.read_text()
        if '@router.get("/health")' in content or '"/health"' in content:
            health_found = True
    
    assert health_found, (
        "Health endpoint not found in codebase. "
        "Expected @app.get('/health') or @router.get('/health') in src/index.py or src/routes/system.py"
    )

