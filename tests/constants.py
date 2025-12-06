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

# Performance thresholds (in seconds)
# These represent acceptable maximum times for critical user flows
PAGE_LOAD_MAX_TIME = 5.0  # Maximum acceptable page load time
SEARCH_OPERATION_MAX_TIME = 3.0  # Maximum acceptable search operation time
FORM_SUBMIT_MAX_TIME = 5.0  # Maximum acceptable form submission time
RATING_CALCULATION_MAX_TIME = 60.0  # Maximum acceptable rating calculation time (already used in test)
NAVIGATION_MAX_TIME = 2.0  # Maximum acceptable navigation time between pages

