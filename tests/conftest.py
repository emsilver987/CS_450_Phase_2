"""
Pytest configuration and fixtures
"""
import sys
from pathlib import Path
import logging
from unittest.mock import patch
import pytest

# Register pytest-asyncio plugin explicitly
pytest_plugins = ["pytest_asyncio"]

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
