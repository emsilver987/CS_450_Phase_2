"""
Pytest configuration and fixtures
"""
import sys
from pathlib import Path
import logging
from unittest.mock import patch, MagicMock
import types
import pytest

# Check for httpx (required by fastapi.testclient.TestClient) - MUST be done before any imports
# Starlette.testclient checks for httpx at import time, so we need to mock it early
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    # Create a complete mock module to satisfy starlette.testclient's import check
    # This must happen before any test files import TestClient
    class MockHTTPXTransport:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockHTTPXClient:
        def __init__(self, *args, **kwargs):
            pass
        def request(self, *args, **kwargs):
            raise RuntimeError("httpx not installed - install with: pip install httpx")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    # Create a proper module object (not MagicMock) to satisfy starlette.testclient's import check
    # Starlette.testclient checks for httpx by importing it, so we need a real module object
    # It also needs Response, Request, and other classes
    class MockHTTPXResponse:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockHTTPXRequest:
        def __init__(self, *args, **kwargs):
            pass
    
    # BaseTransport is a base class that starlette.testclient._TestClientTransport inherits from
    class MockBaseTransport:
        def __init__(self, *args, **kwargs):
            pass
    
    # Create submodules that starlette.testclient accesses
    mock_httpx_client_module = types.ModuleType('httpx._client')
    mock_httpx_types_module = types.ModuleType('httpx._types')
    
    # UseClientDefault is a class/type used in type hints
    class MockUseClientDefault:
        pass
    USE_CLIENT_DEFAULT = MockUseClientDefault()
    mock_httpx_client_module.UseClientDefault = MockUseClientDefault
    mock_httpx_client_module.USE_CLIENT_DEFAULT = USE_CLIENT_DEFAULT
    
    # AuthTypes is a type alias used in type hints
    MockAuthTypes = type(None)  # Use NoneType as a placeholder
    mock_httpx_types_module.AuthTypes = MockAuthTypes
    
    mock_httpx_module = types.ModuleType('httpx')
    mock_httpx_module.AsyncClient = MockHTTPXClient
    mock_httpx_module.Client = MockHTTPXClient
    mock_httpx_module.ASGITransport = MockHTTPXTransport
    mock_httpx_module.BaseTransport = MockBaseTransport
    mock_httpx_module.Response = MockHTTPXResponse
    mock_httpx_module.Request = MockHTTPXRequest
    mock_httpx_module._client = mock_httpx_client_module
    mock_httpx_module._types = mock_httpx_types_module
    mock_httpx_module.__version__ = "0.0.0-mock"
    sys.modules['httpx'] = mock_httpx_module
    sys.modules['httpx._client'] = mock_httpx_client_module
    sys.modules['httpx._types'] = mock_httpx_types_module

# Make selenium module available as mock if not installed - MUST be done before test files import it
try:
    import selenium
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    # Create mock selenium module to prevent import errors in test files
    mock_selenium_module = types.ModuleType('selenium')
    mock_selenium_module.webdriver = types.ModuleType('selenium.webdriver')
    mock_selenium_module.webdriver.common = types.ModuleType('selenium.webdriver.common')
    mock_selenium_module.webdriver.common.by = types.ModuleType('selenium.webdriver.common.by')
    mock_selenium_module.webdriver.common.keys = types.ModuleType('selenium.webdriver.common.keys')
    mock_selenium_module.webdriver.support = types.ModuleType('selenium.webdriver.support')
    mock_selenium_module.webdriver.support.ui = types.ModuleType('selenium.webdriver.support.ui')
    mock_selenium_module.webdriver.support.expected_conditions = types.ModuleType('selenium.webdriver.support.expected_conditions')
    mock_selenium_module.webdriver.chrome = types.ModuleType('selenium.webdriver.chrome')
    mock_selenium_module.common = types.ModuleType('selenium.common')
    mock_selenium_module.common.exceptions = types.ModuleType('selenium.common.exceptions')
    
    # Add commonly used classes
    class MockBy:
        ID = "id"
        NAME = "name"
        XPATH = "xpath"
        CSS_SELECTOR = "css selector"
        CLASS_NAME = "class name"
        TAG_NAME = "tag name"
        LINK_TEXT = "link text"
        PARTIAL_LINK_TEXT = "partial link text"
    
    class MockKeys:
        RETURN = "\n"
        ENTER = "\r"
        ESCAPE = "\x1b"
        TAB = "\t"
        BACKSPACE = "\b"
    
    class MockWebDriverWait:
        def __init__(self, driver, timeout, *args, **kwargs):
            self.driver = driver
            self.timeout = timeout
        def until(self, method, message=""):
            raise RuntimeError("selenium not installed - install with: pip install selenium")
        def until_not(self, method, message=""):
            raise RuntimeError("selenium not installed - install with: pip install selenium")
    
    class MockExpectedConditions:
        @staticmethod
        def presence_of_element_located(*args, **kwargs):
            raise RuntimeError("selenium not installed - install with: pip install selenium")
        @staticmethod
        def element_to_be_clickable(*args, **kwargs):
            raise RuntimeError("selenium not installed - install with: pip install selenium")
    
    class MockSeleniumException(Exception):
        pass
    
    mock_selenium_module.webdriver.common.by.By = MockBy
    mock_selenium_module.webdriver.common.keys.Keys = MockKeys
    mock_selenium_module.webdriver.support.ui.WebDriverWait = MockWebDriverWait
    # expected_conditions is imported as a module, not a class
    ec_module = mock_selenium_module.webdriver.support.expected_conditions
    ec_module.presence_of_element_located = MockExpectedConditions.presence_of_element_located
    ec_module.element_to_be_clickable = MockExpectedConditions.element_to_be_clickable
    mock_selenium_module.common.exceptions.NoSuchElementException = MockSeleniumException
    mock_selenium_module.common.exceptions.InvalidSessionIdException = MockSeleniumException
    mock_selenium_module.common.exceptions.TimeoutException = MockSeleniumException
    
    # Add to sys.modules so imports work
    sys.modules['selenium'] = mock_selenium_module
    sys.modules['selenium.webdriver'] = mock_selenium_module.webdriver
    sys.modules['selenium.webdriver.common'] = mock_selenium_module.webdriver.common
    sys.modules['selenium.webdriver.common.by'] = mock_selenium_module.webdriver.common.by
    sys.modules['selenium.webdriver.common.keys'] = mock_selenium_module.webdriver.common.keys
    sys.modules['selenium.webdriver.support'] = mock_selenium_module.webdriver.support
    sys.modules['selenium.webdriver.support.ui'] = mock_selenium_module.webdriver.support.ui
    sys.modules['selenium.webdriver.support.expected_conditions'] = mock_selenium_module.webdriver.support.expected_conditions
    sys.modules['selenium.webdriver.chrome'] = mock_selenium_module.webdriver.chrome
    sys.modules['selenium.common'] = mock_selenium_module.common
    sys.modules['selenium.common.exceptions'] = mock_selenium_module.common.exceptions

# Register pytest-asyncio plugin explicitly (optional - skip if not installed)
try:
    import pytest_asyncio
    pytest_plugins = ["pytest_asyncio"]
except ImportError:
    # pytest_asyncio not installed - tests using async won't work but won't fail collection
    pytest_plugins = []


# Pytest hook to handle missing dependencies during collection
def pytest_collect_file(file_path, parent):
    """Handle import errors during test collection by skipping problematic modules"""
    # This hook runs before pytest imports test files
    # We can't prevent the import, but we can handle errors
    pass


def pytest_configure(config):
    """Configure pytest to handle missing dependencies"""
    # Register custom markers for missing dependencies
    config.addinivalue_line(
        "markers", "skip_if_no_httpx: mark test to skip if httpx is not available"
    )
    config.addinivalue_line(
        "markers", "skip_if_no_selenium: mark test to skip if selenium is not available"
    )
    config.addinivalue_line(
        "markers", "skip_if_no_pytest_asyncio: mark test to skip if pytest_asyncio is not available"
    )

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Patch watchtower globally at import time to catch module-level imports
# This is necessary because src.index initializes logging at module level
watchtower_patcher = patch("watchtower.CloudWatchLogHandler")
MockWatchtower = watchtower_patcher.start()
MockWatchtower.return_value.level = logging.INFO


@pytest.fixture(scope="session", autouse=True)
def cleanup_watchtower_patch():
    """Cleanup the global watchtower patch at the end of the session"""
    yield
    try:
        if watchtower_patcher:
            watchtower_patcher.stop()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(autouse=True)
def fix_logging_handlers_fixture():
    """Fix any logging handlers that are Mocks with Mock levels"""
    from unittest.mock import MagicMock, Mock
    
    # Fix root logger handlers
    root = logging.getLogger()
    for h in root.handlers:
        if isinstance(h, (MagicMock, Mock)):
            # Check if level is a mock
            if isinstance(h.level, (MagicMock, Mock)):
                h.level = logging.INFO
    
    # Fix all other loggers in the logger tree
    for logger_name in logging.Logger.manager.loggerDict:
        logger_obj = logging.getLogger(logger_name)
        if hasattr(logger_obj, 'handlers'):
            for h in logger_obj.handlers:
                if isinstance(h, (MagicMock, Mock)):
                    if isinstance(h.level, (MagicMock, Mock)):
                        h.level = logging.INFO
    yield


def get_test_client(app):
    """
    Helper function to get a TestClient, skipping if httpx is not available.
    Use this instead of directly importing TestClient in test files.
    """
    if HTTPX_AVAILABLE:
        from fastapi.testclient import TestClient
        return TestClient(app)
    else:
        # Return a mock that skips tests when used
        class MockTestClient:
            def __init__(self, app):
                self.app = app
            def __getattr__(self, name):
                def skip_method(*args, **kwargs):
                    pytest.skip("httpx not installed - install with: pip install httpx")
                return skip_method
            def get(self, *args, **kwargs):
                pytest.skip("httpx not installed - install with: pip install httpx")
            def post(self, *args, **kwargs):
                pytest.skip("httpx not installed - install with: pip install httpx")
            def put(self, *args, **kwargs):
                pytest.skip("httpx not installed - install with: pip install httpx")
            def delete(self, *args, **kwargs):
                pytest.skip("httpx not installed - install with: pip install httpx")
            def patch(self, *args, **kwargs):
                pytest.skip("httpx not installed - install with: pip install httpx")
        return MockTestClient(app)
