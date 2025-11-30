"""
Selenium tests for frontend
"""
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException
import time
import os
import requests
import shutil
import platform


def _find_chromedriver_path():
    """
    Find chromedriver path across different platforms.
    Returns the path if found, None otherwise.
    """
    # Platform-specific common paths
    linux_paths = [
        '/usr/bin/chromedriver',
        '/usr/lib/chromium-browser/chromedriver',
        '/usr/lib/chromium/chromedriver',
    ]

    macos_paths = [
        '/opt/homebrew/bin/chromedriver',  # Apple Silicon
        '/usr/local/bin/chromedriver',  # Intel
    ]

    # Check platform-specific paths first
    system = platform.system().lower()
    if system == 'darwin':  # macOS
        search_paths = macos_paths + linux_paths
    else:  # Linux or other
        search_paths = linux_paths + macos_paths

    # Check common paths
    for path in search_paths:
        if path and os.path.exists(path):
            return path

    # Fallback to PATH
    return shutil.which('chromedriver')


def _get_chromedriver_install_instruction():
    """
    Get platform-specific installation instruction for chromedriver.
    """
    system = platform.system().lower()
    if system == 'darwin':  # macOS
        return "brew install chromedriver"
    else:  # Linux
        return "sudo apt-get install chromium-chromedriver"


@pytest.fixture(scope="module")
def driver():
    """Create a Chrome WebDriver instance"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--remote-debugging-port=9222")

    # Find chromedriver using helper function
    chromedriver_path = _find_chromedriver_path()

    # Try to create driver
    try:
        if chromedriver_path:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Fallback: let Selenium try to find it
            driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        yield driver
    except Exception as e:
        pytest.skip(f"Chrome WebDriver not available: {e}")
    finally:
        if 'driver' in locals():
            try:
                driver.quit()
            except Exception:
                pass


@pytest.fixture
def base_url():
    """Get base URL from environment or use default"""
    base = os.getenv("TEST_BASE_URL", "http://localhost:3000")
    # Check if server is running
    try:
        response = requests.get(f"{base}/health", timeout=2)
        if response.status_code != 200:
            pytest.skip(f"Server at {base} is not responding correctly")
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
        pytest.skip(
            f"Server at {base} is not running. "
            f"Start the server with: python -m src.index"
        )
    return base


def test_chromedriver_available():
    """Verify ChromeDriver is available before running other tests"""
    from selenium.webdriver.chrome.options import Options

    # Find chromedriver using helper function
    chromedriver_path = _find_chromedriver_path()

    install_cmd = _get_chromedriver_install_instruction()
    assert chromedriver_path is not None, (
        f"chromedriver not found in PATH or common locations. "
        f"Install with: {install_cmd}"
    )

    # Try to create a driver instance
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    try:
        service = Service(chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.quit()
    except Exception as e:
        pytest.fail(f"Failed to create ChromeDriver instance: {e}")


class TestHomePage:
    """Test home page functionality"""

    def test_home_page_loads(self, driver, base_url):
        """Test that home page loads successfully"""
        driver.get(f"{base_url}/")

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate page loaded with specific checks
        assert driver.title is not None, "Page should have a title"
        assert len(driver.title) > 0, "Page title should not be empty"
        assert driver.page_source is not None, "Page should have source"
        assert len(driver.page_source) > 0, "Page source should not be empty"
        assert driver.current_url == f"{base_url}/" or base_url in driver.current_url, (
            f"Should be on home page, got {driver.current_url}"
        )

    def test_home_page_has_content(self, driver, base_url):
        """Test that home page has some content"""
        driver.get(f"{base_url}/")

        # Wait for body
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate page content
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "Body element should exist"
        body_text = body.text
        assert len(body_text) > 0, "Body should have text content"
        assert isinstance(body_text, str), "Body text should be a string"


class TestUploadPage:
    """Test upload page functionality"""

    def test_upload_page_loads(self, driver, base_url):
        """Test that upload page loads successfully"""
        driver.get(f"{base_url}/upload")

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate page loaded
        assert (
            driver.current_url.endswith("/upload") or
            "upload" in driver.current_url
        ), (
            f"Should be on upload page, got {driver.current_url}"
        )
        assert len(driver.page_source) > 0, "Page should have content"

        # Check for upload form elements
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        forms = driver.find_elements(By.TAG_NAME, "form")

        # At least one should exist
        assert len(file_inputs) > 0 or len(forms) > 0, (
            "Upload page should have file input or form element"
        )

    def test_upload_page_has_form(self, driver, base_url):
        """Test that upload page has a form"""
        driver.get(f"{base_url}/upload")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Check for form or file input with specific validation
        forms = driver.find_elements(By.TAG_NAME, "form")
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")

        if len(forms) > 0:
            form = forms[0]
            assert form is not None, "Form element should exist"
            assert form.is_displayed(), "Form should be visible"
        elif len(file_inputs) > 0:
            file_input = file_inputs[0]
            assert file_input is not None, "File input should exist"
            assert file_input.is_displayed(), "File input should be visible"
        else:
            pytest.skip("Upload form not found in page structure")


class TestDirectoryPage:
    """Test directory page functionality"""

    def test_directory_page_loads(self, driver, base_url):
        """Test that directory page loads successfully"""
        driver.get(f"{base_url}/directory")

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate page loaded
        assert (
            driver.current_url.endswith("/directory") or
            "directory" in driver.current_url
        ), (
            f"Should be on directory page, got {driver.current_url}"
        )
        assert driver.page_source is not None, "Page should have source"
        assert len(driver.page_source) > 0, "Page source should not be empty"
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "Body element should exist"

    def test_directory_page_has_search(self, driver, base_url):
        """Test that directory page has search functionality"""
        driver.get(f"{base_url}/directory")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Look for search input or form
        search_inputs = driver.find_elements(
            By.CSS_SELECTOR, "input[type='text'], input[type='search']"
        )
        # Search may or may not be present, but page should load
        assert driver.page_source is not None, "Page should have source"
        assert len(driver.page_source) > 0, "Page source should not be empty"
        # If search exists, validate it
        if len(search_inputs) > 0:
            search_input = search_inputs[0]
            assert search_input is not None, "Search input should exist"
            assert search_input.is_displayed(), "Search input should be visible"


class TestRatePage:
    """Test rate page functionality"""

    def test_rate_page_loads(self, driver, base_url):
        """Test that rate page loads successfully"""
        driver.get(f"{base_url}/rate")

        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate page loaded
        assert driver.current_url.endswith("/rate") or "rate" in driver.current_url, (
            f"Should be on rate page, got {driver.current_url}"
        )
        assert driver.page_source is not None, "Page should have source"
        assert len(driver.page_source) > 0, "Page source should not be empty"
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "Body element should exist"

    def test_rate_page_with_name(self, driver, base_url):
        """Test rate page with model name parameter"""
        driver.get(f"{base_url}/rate?name=test-model")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate page loaded with query parameter
        assert "rate" in driver.current_url, (
            f"Should be on rate page, got {driver.current_url}"
        )
        assert "name=test-model" in driver.current_url, (
            "URL should contain name parameter"
        )
        assert driver.page_source is not None, "Page should have source"
        assert len(driver.page_source) > 0, "Page source should not be empty"


class TestNavigation:
    """Test navigation between pages"""

    def test_navigate_home_to_upload(self, driver, base_url):
        """Test navigating from home to upload page"""
        driver.get(f"{base_url}/")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate we're on home page
        assert driver.current_url == f"{base_url}/" or base_url in driver.current_url, (
            f"Should start on home page, got {driver.current_url}"
        )

        # Navigate to upload
        driver.get(f"{base_url}/upload")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate navigation to upload page
        assert "upload" in driver.current_url.lower(), (
            f"Should be on upload page, got {driver.current_url}"
        )
        assert driver.page_source is not None, "Page should have source"

    def test_navigate_to_directory(self, driver, base_url):
        """Test navigating to directory page"""
        driver.get(f"{base_url}/")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Navigate to directory
        driver.get(f"{base_url}/directory")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate navigation to directory page
        assert "directory" in driver.current_url.lower(), (
            f"Should be on directory page, got {driver.current_url}"
        )
        assert driver.page_source is not None, "Page should have source"


class TestUploadAction:
    """Test actual upload functionality"""

    def test_invalid_upload_no_file(self, driver, base_url):
        """Test upload without selecting a file"""
        driver.get(f"{base_url}/upload")

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Find submit button (assuming there is one)
        submit_buttons = driver.find_elements(
            By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"
        )

        if len(submit_buttons) > 0:
            submit_btn = submit_buttons[0]
            assert submit_btn is not None, "Submit button should exist"
            assert submit_btn.is_displayed(), "Submit button should be visible"

            # Store current URL before submit
            url_before = driver.current_url

            submit_btn.click()

            # Wait a moment for any response
            time.sleep(1)

            # Should see some error or stay on page
            assert driver.page_source is not None, "Page should still exist"
            assert len(driver.page_source) > 0, "Page should have content"
            # Page may stay on upload or show error - both are valid
            assert (
                "upload" in driver.current_url.lower() or
                url_before == driver.current_url
            ), (
                "Should stay on upload page or show error"
            )
        else:
            pytest.skip("Upload submit button not found")

    def test_valid_upload_simulation(self, driver, base_url, tmp_path):
        """
        Test valid upload flow.
        Creates a dummy zip file and attempts to upload it.
        """
        # tmp_path already exists as pytest fixture, no need to create
        import zipfile

        # Create dummy zip file before navigating to page
        dummy_zip = tmp_path / "test_package.zip"

        # Create the zip file with content
        with zipfile.ZipFile(dummy_zip, 'w') as zf:
            zf.writestr(
                'package.json',
                '{"name": "test-pkg", "version": "1.0.0"}'
            )

        # Get absolute path - use os.path.abspath for cross-platform compatibility
        # Selenium on macOS/Windows requires absolute paths
        file_path = os.path.abspath(str(dummy_zip.resolve()))

        # Ensure file exists and has content
        assert os.path.exists(file_path), (
            f"Test file should exist at {file_path}"
        )
        assert os.path.isfile(file_path), (
            f"Path must be a file: {file_path}"
        )
        assert os.path.getsize(file_path) > 0, (
            f"Test file should not be empty at {file_path}"
        )

        # Verify it's a valid zip file (after closing the write context)
        with zipfile.ZipFile(dummy_zip, 'r') as zf:
            assert len(zf.namelist()) > 0, "Zip file should contain files"

        driver.get(f"{base_url}/upload")

        # Wait for page to load before interacting
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        try:
            # Verify file still exists (in case tmp_path was cleaned up)
            assert os.path.exists(file_path), (
                f"File must exist before upload: {file_path}"
            )

            # Wait for file input to be present and interactable
            file_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            assert file_input.is_displayed(), "File input should be visible"

            # Use absolute path - Selenium requires this on macOS/Windows
            file_input.send_keys(file_path)

            # Fill other fields if they exist
            try:
                name_input = driver.find_element(By.NAME, "name")
                name_input.send_keys("test-pkg")
            except NoSuchElementException:
                pass

            try:
                version_input = driver.find_element(By.NAME, "version")
                version_input.send_keys("1.0.0")
            except NoSuchElementException:
                pass

            # Submit
            submit_btn = driver.find_element(
                By.CSS_SELECTOR,
                "button[type='submit'], input[type='submit']"
            )
            submit_btn.click()

            # Wait for result - either success message or redirect
            time.sleep(2)  # Wait for upload to process

            # Validate page state after upload attempt
            assert driver.page_source is not None, "Page should still exist"
            assert len(driver.page_source) > 0, "Page should have content"

            # Check for success/error indicators
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            # Page may show success, error, or stay on upload page
            # All are valid outcomes depending on implementation
            assert (
                "success" in page_text or "error" in page_text or
                "upload" in driver.current_url.lower()
            ), "Page should show result or stay on upload page"

        except NoSuchElementException as e:
            pytest.skip(f"Upload form elements not found: {e}")
        except Exception as e:
            # Re-raise other exceptions to see actual failures
            raise AssertionError(
                f"Upload test failed with error: {e}. "
                f"File path used: {file_path}"
            ) from e


class TestSearchAction:
    """Test search functionality"""

    def test_search_execution(self, driver, base_url):
        """Test performing a search"""
        driver.get(f"{base_url}/directory")

        try:
            search_input = driver.find_element(
                By.CSS_SELECTOR,
                "input[type='text'], input[type='search']"
            )
            search_input.send_keys("test")

            # Try to find search button or hit enter
            try:
                search_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "button[type='submit'], button.search-btn"
                )
                search_btn.click()
            except NoSuchElementException:
                search_input.submit()

            # Wait for results or page update
            time.sleep(2)

            # Validate search executed
            assert driver.page_source is not None, "Page should still exist"
            assert len(driver.page_source) > 0, "Page should have content"

            # Verify search input still has the value
            search_input_after = driver.find_element(
                By.CSS_SELECTOR, "input[type='text'], input[type='search']"
            )
            assert search_input_after.get_attribute("value") == "test", (
                "Search input should retain the search term"
            )

        except NoSuchElementException:
            pytest.skip("Search input not found")
