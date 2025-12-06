"""
Pytest fixtures for Selenium integration tests
"""
import os
import socket
import threading
import time

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from tests.constants import (
    DEFAULT_PORT,
    WEBDRIVER_IMPLICIT_WAIT
)
from tests.utils.chromedriver import (
    find_chromedriver_path,
)


def _find_free_port():
    """
    Find a free port for remote debugging.
    Returns a port number that is available.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


# Thread-safe module-level cache for driver instances
# Key format: (module_name, thread_id) -> driver
_driver_cache = {}
_cache_lock = threading.Lock()
_driver_finalizers = {}


def _get_cache_key(request):
    """Generate a unique cache key for the current test module and thread."""
    module_name = request.module.__name__ if request.module else "unknown"
    thread_id = threading.get_ident()
    return (module_name, thread_id)


@pytest.fixture(scope="module")
def driver(request):
    """Create a Chrome WebDriver instance with proper isolation."""
    cache_key = _get_cache_key(request)

    # Check if driver already exists in cache for this module/thread
    with _cache_lock:
        if cache_key in _driver_cache:
            driver_instance = _driver_cache[cache_key]
            yield driver_instance
            return

    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")

    # Use dynamic port allocation to avoid conflicts
    debug_port = _find_free_port()
    chrome_options.add_argument(f"--remote-debugging-port={debug_port}")

    # Find chromedriver using helper function
    chromedriver_path = find_chromedriver_path()

    # Initialize driver to None for reliable cleanup check
    driver_instance = None
    driver_created = False

    # Register finalizer for this specific cache key
    if cache_key not in _driver_finalizers:
        def cleanup_driver():
            with _cache_lock:
                if cache_key in _driver_cache and _driver_cache[cache_key] is not None:
                    cached_driver = _driver_cache[cache_key]
                    try:
                        cached_driver.quit()
                        time.sleep(0.5)
                    except Exception as e:
                        # Log but don't fail - cleanup errors shouldn't break tests
                        print(
                            f"Warning: Error during driver cleanup "
                            f"for {cache_key}: {e}"
                        )
                    finally:
                        _driver_cache.pop(cache_key, None)
                        _driver_finalizers.pop(cache_key, None)

        _driver_finalizers[cache_key] = cleanup_driver
        # Register at session scope to ensure cleanup
        request.session.addfinalizer(cleanup_driver)

    # Try to create driver
    try:
        if chromedriver_path:
            service = Service(chromedriver_path)
            driver_instance = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Fallback: let Selenium try to find it
            driver_instance = webdriver.Chrome(options=chrome_options)

        driver_instance.implicitly_wait(WEBDRIVER_IMPLICIT_WAIT)
        driver_created = True

        # Store in cache with thread-safe lock
        with _cache_lock:
            _driver_cache[cache_key] = driver_instance

        yield driver_instance
    except Exception as e:
        pytest.skip(f"Chrome WebDriver not available: {e}")
    finally:
        # Ensure cleanup even if driver creation fails mid-way (created but not cached)
        if driver_instance is not None and not driver_created:
            try:
                driver_instance.quit()
            except Exception as e:
                print(f"Warning: Error cleaning up failed driver: {e}")


@pytest.fixture(autouse=True)
def reset_driver_state(driver, request):
    """
    Reset driver state before each test to prevent state leakage.
    This ensures each test starts from a clean state even when using module-scoped driver.
    """
    # Skip if driver fixture was skipped (not available)
    if driver is None:
        yield
        return
    
    # Check if driver session is still valid before attempting reset
    try:
        # Test if session is valid by getting current URL
        _ = driver.current_url
        session_valid = True
    except Exception:
        # Session is invalid - try to create a new one
        session_valid = False
    
    # If session is invalid, try to recreate driver
    if not session_valid:
        try:
            # Try to get a valid session by attempting a simple operation
            driver.get("data:text/html,<html><body></body></html>")
            session_valid = True
        except Exception as e:
            # Session is completely dead, skip reset
            # Test should handle this by skipping or failing appropriately
            yield
            return
    
    # Navigate to a blank page to reset state
    # Using data URI ensures we start fresh without loading any app state
    try:
        driver.get("data:text/html,<html><body></body></html>")
    except Exception:
        # If navigation fails, session might be invalid - skip reset
        yield
        return
    
    # Clear cookies and local storage to ensure clean state
    try:
        driver.delete_all_cookies()
    except Exception:
        # Some drivers may not support cookie deletion, ignore
        pass
    yield
    # Optional: Clean up after test if needed
    # For now, we rely on the reset before each test


@pytest.fixture
def base_url():
    """Get base URL from environment or use default"""
    base = os.getenv("TEST_BASE_URL", f"http://localhost:{DEFAULT_PORT}")
    # Check if server is running
    try:
        response = requests.get(f"{base}/health", timeout=2)
        if response.status_code != 200:
            pytest.skip(f"Server at {base} is not responding correctly")
    except requests.exceptions.Timeout:
        pytest.skip(
            f"Server at {base} is not running. "
            f"Start the server with: python -m src.index"
        )
    except requests.exceptions.RequestException:
        pytest.skip(
            f"Server at {base} is not running. "
            f"Start the server with: python -m src.index"
        )
    return base

