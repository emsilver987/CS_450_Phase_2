# Testing Guide

This guide covers how to run tests locally, set up the testing environment, and troubleshoot common issues.

## Overview

The test suite includes:

- **Unit tests**: Fast, isolated tests in `tests/unit/`
- **Integration tests**: Tests that require a running server, including Selenium frontend tests in `tests/integration/`

## Running Tests

### Unit Tests Only

```bash
# Run all unit tests
pytest tests/unit/

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run with coverage (terminal output, exclude populate_registry tests)
pytest --cov=src --cov-report=term-missing -k "not populate_registry"
```

### Integration Tests

Integration tests require a running server and ChromeDriver.

```bash
# Start the server first
uvicorn src.entrypoint:app --host 0.0.0.0 --port 3000

# In another terminal, run integration tests
pytest tests/integration/ -v

# Exclude TestRegistryPopulation tests (including 500 models test)
pytest tests/integration/ -k "not TestRegistryPopulation" -v

   # Or run only Selenium frontend tests
   pytest tests/integration/test_frontend_*.py -v

   # Run specific page tests
   pytest tests/integration/test_frontend_home.py -v
   pytest tests/integration/test_frontend_directory.py -v
```

### All Tests

```bash
# Run all tests (unit + integration)
pytest

# Exclude integration tests for faster runs
pytest -m "not integration"
```

## Selenium Test Setup

Selenium tests require both Chrome/Chromium browser and ChromeDriver to be installed on your system. The tests run in headless mode and automatically locate the browser driver.

### Prerequisites

1. **Python dependencies**: Install test dependencies from `requirements-dev.txt`

   ```bash
   pip install -r requirements-dev.txt
   ```

   This includes:
   - `selenium>=4.38.0` - Browser automation framework
   - `webdriver-manager>=4.0.0` - Automatic driver management
   - `pytest` - Testing framework
   - `pytest-asyncio` - Async test support
   - `httpx` - HTTP client for testing

2. **Chrome or Chromium browser**: Must be installed on your system
3. **ChromeDriver**: Must be installed separately and match your browser version

### Browser Installation

Selenium tests require Chrome or Chromium browser to be installed.

#### macOS

```bash
# Install Chrome browser (if not already installed)
brew install --cask google-chrome

# Or install Chromium
brew install chromium
```

#### Linux (Ubuntu/Debian)

```bash
# Install Chromium browser
sudo apt-get update
sudo apt-get install -y chromium-browser
```

#### Windows

Download and install [Google Chrome](https://www.google.com/chrome/) from the official website.

### ChromeDriver Installation

ChromeDriver must be installed separately and should match your Chrome/Chromium browser version. The tests will automatically search common installation paths.

#### macOS

```bash
# Using Homebrew (recommended)
brew install chromedriver

# After installation, you may need to allow chromedriver to run:
# System Preferences → Security & Privacy → Allow chromedriver
```

**Installation paths:**

- Apple Silicon Macs: `/opt/homebrew/bin/chromedriver`
- Intel Macs: `/usr/local/bin/chromedriver`

**Note**: Homebrew installs ChromeDriver that matches your installed Chrome version automatically.

#### Linux (Ubuntu/Debian)

```bash
# Install chromedriver (install chromium-browser first if not already installed)
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver

# Verify installation
chromedriver --version
```

**Installation paths:**

- `/usr/lib/chromium-browser/chromedriver` (most common)
- `/usr/bin/chromedriver`

**Note**: `chromium-chromedriver` automatically matches your `chromium-browser` version.

#### Windows

1. **Check your Chrome version**: Open Chrome → Settings → About Chrome
2. **Download ChromeDriver**: Visit [ChromeDriver Downloads](https://chromedriver.chromium.org/downloads) and download the matching version
3. **Install ChromeDriver**:
   - Extract the ZIP file
   - Place `chromedriver.exe` in a directory in your PATH (e.g., `C:\Windows\System32`)
   - Or place it in your project directory

**Alternative (using webdriver-manager)**:
The `webdriver-manager` package can automatically download and manage ChromeDriver, but manual installation is recommended for better control.

### Version Compatibility

- ChromeDriver version must match your Chrome/Chromium browser version
- On macOS with Homebrew: ChromeDriver automatically matches your Chrome version
- On Linux: `chromium-chromedriver` automatically matches `chromium-browser` version
- On Windows: You must manually match versions when downloading from ChromeDriver Downloads

**Checking versions:**

```bash
# Check Chrome browser version
google-chrome --version  # Linux
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version  # macOS

# Check ChromeDriver version
chromedriver --version
```

### Verifying Installation

Before running Selenium tests, verify that both Chrome/Chromium browser and ChromeDriver are installed:

```bash
# Check if Chrome/Chromium browser is installed
google-chrome --version  # Linux
chromium --version  # Linux (if using Chromium)
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version  # macOS

# Check if chromedriver is in PATH
which chromedriver
chromedriver --version

# Verify versions match (ChromeDriver version should match Chrome version major number)
# For example: Chrome 120.x should use ChromeDriver 120.x
```

**Running the verification test:**

```bash
# Run any frontend test to verify ChromeDriver availability
pytest tests/integration/test_frontend_home.py -v
```

Tests will automatically check if ChromeDriver can be found and initialized correctly.

### Running Selenium Tests Locally

1. **Start the server**:

   ```bash
   # Set environment variables if needed
   export TEST_BASE_URL=http://localhost:3000
   export ENABLE_AUTH=false  # Or true if testing auth

   # Start server
   uvicorn src.entrypoint:app --host 0.0.0.0 --port 3000
   ```

2. **In another terminal, run tests**:

   ```bash
   # Set base URL if different from default
   export TEST_BASE_URL=http://localhost:3000

   # Run Selenium frontend tests
   pytest tests/integration/test_frontend_*.py -v

   # Run only accessibility tests
   pytest tests/integration/test_frontend_*.py::Test*FrontendAccessibility -v

   # Run only UI functionality tests
   pytest tests/integration/test_frontend_*.py::Test*FrontendUI -v
   ```

3. **Tests will automatically**:
   - Find ChromeDriver using platform-specific paths
   - Check server health endpoint before running
   - Skip tests if server is unavailable

## CI Workflow

The CI workflow (`.github/workflows/ci.yml`) runs tests in three jobs:

1. **install**: Installs dependencies (with pip caching)
2. **test**: Runs unit tests
3. **selenium-test**:
   - Installs system dependencies (chromium-browser, chromium-chromedriver)
   - Starts server in background
   - Waits for server health check
   - Runs Selenium tests
   - Captures server logs on failure

### CI Test Configuration

- **Server port**: 3000 (configurable via `TEST_BASE_URL`)
- **Server startup delay**: 2 seconds (reduced from 5s)
- **Health check timeout**: 30 retries with 1s delay
- **WebDriver wait timeout**: 10 seconds

## Troubleshooting

### ChromeDriver Not Found

**Error**: `chromedriver not found in PATH or common locations`

**Solutions**:

1. Install ChromeDriver (see installation instructions above)
2. Add ChromeDriver to PATH
3. Verify installation: `chromedriver --version`
4. Check test output for suggested installation command

### Server Not Running

**Error**: `Server at http://localhost:3000 is not running`

**Solutions**:

1. Start the server: `uvicorn src.entrypoint:app --host 0.0.0.0 --port 3000`
2. Check if port 3000 is already in use: `lsof -i :3000`
3. Verify health endpoint: `curl http://localhost:3000/health`
4. Set `TEST_BASE_URL` environment variable if using different port

### Tests Timeout

**Error**: `TimeoutException` or tests hang

**Solutions**:

1. Check server logs for errors
2. Verify server is responding: `curl http://localhost:3000/health`
3. Increase timeout in `tests/constants.py` (not recommended for CI)
4. Check ChromeDriver version matches Chrome browser version

### Port Already in Use

**Error**: `Address already in use` when starting server

**Solutions**:

1. Find and kill process using port 3000:
   ```bash
   lsof -ti:3000 | xargs kill -9
   ```
2. Use a different port and set `TEST_BASE_URL` accordingly
3. Check for zombie server processes: `ps aux | grep uvicorn`

### CI Test Failures

**Common issues**:

1. **Server fails to start**:
   - Check server logs artifact in CI
   - Verify entrypoint module imports correctly
   - Check for missing environment variables

2. **ChromeDriver version mismatch**:
   - CI installs `chromium-chromedriver` which should match `chromium-browser`
   - If mismatch occurs, update CI workflow to install specific versions

3. **Flaky tests**:
   - Tests use `WebDriverWait` instead of `time.sleep()` for reliability
   - If still flaky, check network conditions or server response times

### Viewing Server Logs in CI

When tests fail in CI:

1. Check the "Capture server logs on failure" step output
2. Download the "server-logs" artifact
3. Review logs for errors or warnings

## Test Structure

### Test Organization

- `tests/unit/`: Unit tests (no external dependencies)
- `tests/integration/`: Integration tests (require server)
  - `test_frontend_*.py`: Selenium frontend tests (one file per page)
    - `test_frontend_home.py`: Homepage tests
    - `test_frontend_directory.py`: Directory page tests
    - `test_frontend_upload.py`: Upload page tests
    - `test_frontend_license_check.py`: License check page tests
    - `test_frontend_lineage.py`: Lineage page tests
    - `test_frontend_rate.py`: Rate page tests
    - `test_frontend_size_cost.py`: Size/cost page tests
  - `test_accessibility_base.py`: Shared base class for accessibility tests
  - `conftest.py`: Shared fixtures for integration tests
  - `test_ci_environment.py`: CI environment validation

### Test Utilities

- `tests/utils/chromedriver.py`: Shared ChromeDriver path finding logic
- `tests/constants.py`: Test constants (timeouts, ports, etc.)
- `tests/conftest.py`: Pytest configuration and fixtures

### Test Fixtures

- `driver`: Module-scoped Chrome WebDriver instance (reused across tests)
- `base_url`: Base URL for tests (from `TEST_BASE_URL` env var or default)

## Best Practices

1. **Use WebDriverWait instead of time.sleep()**: More reliable and faster
2. **Check server health before tests**: Prevents false failures
3. **Clean up resources**: Tests automatically clean up driver instances
4. **Use constants**: Import from `tests/constants.py` instead of magic numbers
5. **Skip gracefully**: Use `pytest.skip()` when dependencies are missing

## Environment Variables

| Variable        | Default                 | Description                          |
| --------------- | ----------------------- | ------------------------------------ |
| `TEST_BASE_URL` | `http://localhost:3000` | Base URL for integration tests       |
| `ENABLE_AUTH`   | `false`                 | Enable JWT authentication middleware |
| `JWT_SECRET`    | (none)                  | JWT secret key (enables auth if set) |
| `CI`            | (none)                  | Set to `true` in CI environment      |

## Integration Test Documentation

### Running Integration Tests

Integration tests verify the system end-to-end, including:

- Frontend UI functionality (Selenium tests)
- API endpoint behavior
- Database interactions
- File upload/download workflows

#### Prerequisites

1. **Install test dependencies**:

   ```bash
   pip install -r requirements-dev.txt
   ```

2. **Start the server**:

   ```bash
   uvicorn src.entrypoint:app --host 0.0.0.0 --port 3000
   ```

3. **Run integration tests**:

   ```bash
   # All integration tests
   pytest tests/integration/ -v

   # Only Selenium frontend tests
   pytest tests/integration/test_selenium_frontend.py -v -m selenium

   # Specific test file
   pytest tests/integration/test_directory.py -v
   ```

### Test Markers

Tests use pytest markers for organization:

- `@pytest.mark.integration` - Integration tests requiring server (automatically applied via `pytestmark`)
- `@pytest.mark.skipif` - Conditional test skipping

### Test Structure

Frontend tests are organized by page, with two test classes per page:

1. **Accessibility Tests** (`Test*FrontendAccessibility`): WCAG 2.1 Level AA compliance tests
   - Language attributes
   - Page titles
   - Heading hierarchy
   - Form labels and ARIA attributes
   - Keyboard navigation
   - Focus indicators

2. **UI Functionality Tests** (`Test*FrontendUI`): Frontend UI behavior tests
   - Page loading
   - Form interactions
   - Search functionality
   - Results display

Example:

```python
class TestHomeFrontendAccessibility:
    """Test WCAG 2.1 Level AA compliance on homepage frontend."""

    def test_language_attribute(self, driver, base_url):
        driver.get(base_url)
        html = driver.find_element(By.TAG_NAME, "html")
        assert html.get_attribute("lang") == "en"
```

### Running Specific Test Types

```bash
# Run all frontend tests
pytest tests/integration/test_frontend_*.py -v

# Run only accessibility tests
pytest tests/integration/test_frontend_*.py::Test*FrontendAccessibility -v

# Run only UI functionality tests
pytest tests/integration/test_frontend_*.py::Test*FrontendUI -v

# Run tests for a specific page
pytest tests/integration/test_frontend_home.py -v
```

### Integration Test Structure

```
tests/integration/
├── conftest.py                   # Shared fixtures (driver, base_url)
├── test_accessibility_base.py   # Base class for accessibility tests
├── test_frontend_*.py           # Frontend UI tests (one per page)
│   ├── test_frontend_home.py
│   ├── test_frontend_directory.py
│   ├── test_frontend_upload.py
│   ├── test_frontend_license_check.py
│   ├── test_frontend_lineage.py
│   ├── test_frontend_rate.py
│   └── test_frontend_size_cost.py
├── test_directory.py            # Directory API tests
├── test_upload.py               # Upload API tests
└── test_package_system.py       # Package management tests
```

### Best Practices for Integration Tests

1. **Use WebDriverWait**: Always wait for elements instead of using `time.sleep()`

   ```python
   from selenium.webdriver.support.ui import WebDriverWait
   from selenium.webdriver.support import expected_conditions as EC

   element = WebDriverWait(driver, 10).until(
       EC.presence_of_element_located((By.ID, "my-element"))
   )
   ```

2. **Check server health**: Tests automatically verify server is running before execution

3. **Clean up resources**: Tests should clean up any created data or resources

4. **Use fixtures**: Leverage pytest fixtures for common setup (driver, base_url, etc.)

5. **Skip gracefully**: Use `pytest.skip()` when dependencies are missing

## Additional Resources

- [Selenium Python Documentation](https://selenium-python.readthedocs.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [ChromeDriver Downloads](https://chromedriver.chromium.org/downloads)
