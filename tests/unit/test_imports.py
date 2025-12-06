"""
Test that all test module imports work correctly
"""
import pytest


def test_tests_constants_importable():
    """Verify tests.constants can be imported"""
    from tests.constants import (
        DEFAULT_PORT,
        WEBDRIVER_WAIT_TIMEOUT,
        WEBDRIVER_IMPLICIT_WAIT,
        SERVER_STARTUP_DELAY,
        HEALTH_CHECK_TIMEOUT,
        HEALTH_CHECK_RETRY_DELAY,
    )
    assert DEFAULT_PORT == 3000
    assert WEBDRIVER_WAIT_TIMEOUT == 10
    assert WEBDRIVER_IMPLICIT_WAIT == 10
    assert SERVER_STARTUP_DELAY == 2
    assert HEALTH_CHECK_TIMEOUT == 30
    assert HEALTH_CHECK_RETRY_DELAY == 1


def test_tests_utils_importable():
    """Verify tests.utils can be imported"""
    from tests.utils.chromedriver import find_chromedriver_path, get_chromedriver_install_instruction
    
    # Functions should be callable
    assert callable(find_chromedriver_path)
    assert callable(get_chromedriver_install_instruction)
    
    # Should return something (path or None, instruction string)
    install_cmd = get_chromedriver_install_instruction()
    assert isinstance(install_cmd, str)
    assert len(install_cmd) > 0

