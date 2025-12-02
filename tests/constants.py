"""
Test constants for Selenium tests and CI workflow
"""

# Server configuration
DEFAULT_PORT = 3000
SERVER_STARTUP_DELAY = 2  # Reduced from 5s for faster CI
HEALTH_CHECK_TIMEOUT = 30
HEALTH_CHECK_RETRY_DELAY = 1

# WebDriver configuration
WEBDRIVER_WAIT_TIMEOUT = 10
WEBDRIVER_IMPLICIT_WAIT = 10

