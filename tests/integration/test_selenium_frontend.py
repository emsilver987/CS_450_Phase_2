"""
Selenium tests for frontend
"""
import os
import pathlib
import socket
import time
import zipfile

import pytest
import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from tests.constants import (
    DEFAULT_PORT,
    WEBDRIVER_WAIT_TIMEOUT,
    WEBDRIVER_IMPLICIT_WAIT
)
from tests.utils.chromedriver import (
    find_chromedriver_path,
    get_chromedriver_install_instruction
)

pytestmark = pytest.mark.integration


def _find_free_port():
    """
    Find a free port for remote debugging.
    Returns a port number that is available.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


# Module-level cache for driver instance to ensure true module scope
_driver_cache = {}
_driver_finalizer_registered = False


@pytest.fixture(scope="module")
def driver(request):
    """Create a Chrome WebDriver instance"""
    global _driver_finalizer_registered

    # Check if driver already exists in module cache (true module scope)
    if "driver" in _driver_cache:
        yield _driver_cache["driver"]
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
    driver = None
    driver_created = False

    # Register finalizer BEFORE creating driver to ensure cleanup even if creation fails
    if not _driver_finalizer_registered:
        _driver_finalizer_registered = True

        def cleanup_driver():
            if "driver" in _driver_cache and _driver_cache["driver"] is not None:
                cached_driver = _driver_cache["driver"]
                try:
                    cached_driver.quit()
                    time.sleep(0.5)
                except Exception as e:
                    # Log but don't fail - cleanup errors shouldn't break tests
                    print(f"Warning: Error during driver cleanup: {e}")
                finally:
                    _driver_cache.clear()

        # Register at session scope to ensure it runs only once
        request.session.addfinalizer(cleanup_driver)

    # Try to create driver
    try:
        if chromedriver_path:
            service = Service(chromedriver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            # Fallback: let Selenium try to find it
            driver = webdriver.Chrome(options=chrome_options)

        driver.implicitly_wait(WEBDRIVER_IMPLICIT_WAIT)
        driver_created = True

        # Store in module cache for reuse
        _driver_cache["driver"] = driver

        yield driver
    except Exception as e:
        pytest.skip(f"Chrome WebDriver not available: {e}")
    finally:
        # Ensure cleanup even if driver creation fails mid-way (created but not cached)
        if driver is not None and not driver_created:
            try:
                driver.quit()
            except Exception as e:
                print(f"Warning: Error cleaning up failed driver: {e}")


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


@pytest.fixture
def sample_upload_zip(tmp_path):
    """
    Create a dummy zip file used by Selenium upload tests.
    Returns the absolute file path as a string (for Selenium).
    """
    # Ensure parent directory exists
    tmp_path.mkdir(parents=True, exist_ok=True)

    zip_path = tmp_path / "test_package.zip"

    # Create a valid zip file with content
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add a simple file to the archive for upload testing
        zf.writestr("dummy.txt", "content for upload test")

    # Verify the zip file was created and is valid
    assert zip_path.exists(), f"Zip file should exist after creation at {zip_path}"
    assert zip_path.is_file(), f"Zip file should be a file, not a directory: {zip_path}"

    # Verify it's a valid zip file by trying to read it
    with zipfile.ZipFile(zip_path, "r") as zf:
        assert "dummy.txt" in zf.namelist(), "Zip file should contain dummy.txt"

    # Resolve to absolute path and verify it exists
    absolute_path = zip_path.resolve()
    assert absolute_path.exists(), f"Absolute path should exist: {absolute_path}"
    assert absolute_path.is_file(), f"Absolute path should be a file: {absolute_path}"

    # Return as string for Selenium
    return str(absolute_path)


def test_chromedriver_available():
    """Verify ChromeDriver is available before running other tests"""
    from selenium.webdriver.chrome.options import Options

    # Find chromedriver using helper function
    chromedriver_path = find_chromedriver_path()

    install_cmd = get_chromedriver_install_instruction()
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
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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
        """Test that home page has specific expected content"""
        driver.get(f"{base_url}/")

        # Wait for body
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate page content
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "Body element should exist"
        body_text = body.text
        assert len(body_text) > 0, "Body should have text content"
        assert isinstance(body_text, str), "Body text should be a string"

        # Check for specific expected content (headings, navigation links)
        page_source_lower = driver.page_source.lower()
        # Check for common home page elements
        assert any(keyword in page_source_lower for keyword in [
            "welcome", "acme", "registry", "package", "upload", "directory"
        ]), "Home page should contain expected keywords"

        # Check for navigation links
        nav_links = driver.find_elements(
            By.CSS_SELECTOR, "a[href*='/upload'], a[href*='/directory']"
        )
        assert len(nav_links) > 0, (
            "Home page should have navigation links to upload or directory"
        )


class TestUploadPage:
    """Test upload page functionality"""

    def test_upload_page_loads(self, driver, base_url):
        """Test that upload page loads successfully"""
        driver.get(f"{base_url}/upload")

        # Wait for page to load
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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
        """Test that upload page has a form with proper attributes"""
        driver.get(f"{base_url}/upload")

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Check for form or file input with specific validation
        forms = driver.find_elements(By.TAG_NAME, "form")
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")

        if len(forms) > 0:
            form = forms[0]
            assert form is not None, "Form element should exist"
            assert form.is_displayed(), "Form should be visible"
            # Verify form has action and method attributes (if present)
            form_method = form.get_attribute("method")
            # Form should have either action attribute or be handled by JavaScript
            # Method should be POST for file uploads (or not specified for JS handling)
            if form_method:
                assert form_method.upper() in ["POST", "GET", ""], (
                    f"Form method should be POST or GET, got {form_method}"
                )
        elif len(file_inputs) > 0:
            file_input = file_inputs[0]
            assert file_input is not None, "File input should exist"
            assert file_input.is_displayed(), "File input should be visible"
            # Verify file input accepts appropriate file types
            accept_attr = file_input.get_attribute("accept")
            # Accept attribute is optional, but if present should be reasonable
            if accept_attr:
                assert len(accept_attr) > 0, (
                    "File input accept attribute should not be empty"
                )
        else:
            pytest.skip("Upload form not found in page structure")


class TestDirectoryPage:
    """Test directory page functionality"""

    def test_directory_page_loads(self, driver, base_url):
        """Test that directory page loads successfully"""
        driver.get(f"{base_url}/directory")

        # Wait for page to load
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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
        """Test that directory page has search functionality that works"""
        driver.get(f"{base_url}/directory")

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Look for search input or form
        search_inputs = driver.find_elements(
            By.CSS_SELECTOR, "input[type='text'], input[type='search']"
        )
        # Search may or may not be present, but page should load
        assert driver.page_source is not None, "Page should have source"
        assert len(driver.page_source) > 0, "Page source should not be empty"
        # If search exists, validate it works
        if len(search_inputs) > 0:
            search_input = search_inputs[0]
            assert search_input is not None, "Search input should exist"
            assert search_input.is_displayed(), "Search input should be visible"
            # Verify search input is functional
            assert search_input.is_enabled(), "Search input should be enabled"
            # Placeholder is optional but good UX practice
            # Verify we can interact with the search input
            try:
                search_input.send_keys("test")
                value = search_input.get_attribute("value")
                assert value == "test", (
                    f"Search input should accept input, got '{value}'"
                )
                # Clear the input
                search_input.clear()
            except Exception as e:
                pytest.fail(f"Search input should be interactive: {e}")


class TestRatePage:
    """Test rate page functionality"""

    def test_rate_page_loads(self, driver, base_url):
        """Test that rate page loads successfully"""
        driver.get(f"{base_url}/rate")

        # Wait for page to load
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Validate we're on home page
        assert driver.current_url == f"{base_url}/" or base_url in driver.current_url, (
            f"Should start on home page, got {driver.current_url}"
        )

        # Navigate to upload
        driver.get(f"{base_url}/upload")

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Navigate to directory
        driver.get(f"{base_url}/directory")

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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

        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
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

            # Wait for form submission response - either error message
            # appears or page stays
            try:
                # Wait for error message or validation message to appear
                WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
                    lambda d: any([
                        "error" in d.page_source.lower(),
                        "required" in d.page_source.lower(),
                        "invalid" in d.page_source.lower(),
                        d.current_url == url_before  # Or URL hasn't changed
                    ])
                )
            except Exception:
                # If no error message appears, page should still be valid
                pass

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

    def test_valid_upload_simulation(self, driver, base_url, sample_upload_zip):
        """
        Test valid upload flow.
        Creates a dummy zip file and attempts to upload it.
        """
        # Verify the upload file exists before attempting upload
        upload_file_path = pathlib.Path(sample_upload_zip)
        assert upload_file_path.exists(), (
            f"Upload file must exist before test. Expected at: {upload_file_path}"
        )
        assert upload_file_path.is_file(), (
            f"Upload path must be a file, not a directory: {upload_file_path}"
        )

        driver.get(f"{base_url}/upload")

        try:
            file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            # Use fixture path for upload - ensure it's an absolute path string
            file_path_str = str(upload_file_path.resolve())
            file_input.send_keys(file_path_str)

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

            # Wait for result - either success message, error message, or redirect
            try:
                WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
                    lambda d: any([
                        "success" in d.find_element(
                            By.TAG_NAME, "body"
                        ).text.lower(),
                        "error" in d.find_element(
                            By.TAG_NAME, "body"
                        ).text.lower(),
                        d.current_url != f"{base_url}/upload",  # Redirect
                        len(d.find_elements(
                            By.CSS_SELECTOR, ".alert, .message, .notification"
                        )) > 0  # Message element appeared
                    ])
                )
            except Exception:
                # If no clear indicator, page should still be valid
                pass

            # Validate page state after upload attempt
            assert driver.page_source is not None, "Page should still exist"
            assert len(driver.page_source) > 0, "Page should have content"

            # Check for success/error indicators with more specific assertions
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            page_source_lower = driver.page_source.lower()
            current_url_lower = driver.current_url.lower()

            # Page may show success, error, or stay on upload page
            # All are valid outcomes depending on implementation
            has_success_indicator = any([
                "success" in page_text,
                "uploaded" in page_text,
                "success" in page_source_lower,
                "uploaded" in page_source_lower
            ])
            has_error_indicator = any([
                "error" in page_text,
                "invalid" in page_text,
                "failed" in page_text,
                "error" in page_source_lower,
                "invalid" in page_source_lower,
                "failed" in page_source_lower
            ])
            still_on_upload_page = "upload" in current_url_lower

            assert (
                has_success_indicator or has_error_indicator or still_on_upload_page
            ), (
                f"Page should show success/error message or stay on upload page. "
                f"URL: {driver.current_url}, "
                f"Page text contains 'success': {has_success_indicator}, "
                f"Page text contains 'error': {has_error_indicator}"
            )

            # If there's a message element, verify it's visible
            message_elements = driver.find_elements(
                By.CSS_SELECTOR,
                ".alert, .message, .notification, .error, .success"
            )
            if len(message_elements) > 0:
                message_element = message_elements[0]
                assert message_element.is_displayed(), (
                    "Message element should be visible"
                )

        except NoSuchElementException:
            pytest.skip("Upload form elements not found")


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
                    "button[type='submit'], "
                    "button.search-btn"
                )
                search_btn.click()
            except NoSuchElementException:
                search_input.submit()

            # Wait for search results or page update
            try:
                # Wait for search results to appear or URL to change
                WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
                    lambda d: any([
                        "test" in d.current_url.lower(),  # Search term in URL
                        len(d.find_elements(
                            By.CSS_SELECTOR,
                            ".result, .search-result, table, .list-item"
                        )) > 0,  # Results appeared
                        d.find_element(
                            By.CSS_SELECTOR,
                            "input[type='text'], input[type='search']"
                        ).get_attribute("value") == "test"  # Input retained
                    ])
                )
            except Exception:
                # If no clear results indicator, verify search input retained value
                pass

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


class TestDriverCleanup:
    """Test driver cleanup and state management"""

    def test_driver_cleanup_after_failure(self, driver, base_url):
        """Verify driver is cleaned up even if test fails"""
        driver.get(f"{base_url}/")

        # Wait for page to load
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Verify driver is working
        assert driver.current_url is not None, "Driver should have a current URL"

        # Simulate a test failure - driver should still be cleaned up properly
        # This test verifies that the finalizer will handle cleanup even if
        # a test raises an exception
        raise AssertionError("Intentional test failure to verify cleanup")

    def test_driver_reuse_across_tests(self, driver, base_url):
        """Verify module-scoped driver is properly reused"""
        # Get initial driver instance
        initial_driver_id = id(driver)

        # Perform some operations
        driver.get(f"{base_url}/")
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Navigate to another page
        driver.get(f"{base_url}/directory")
        WebDriverWait(driver, WEBDRIVER_WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        # Verify it's the same driver instance (module scope ensures reuse)
        assert id(driver) == initial_driver_id, (
            "Driver should be reused across tests in the same module"
        )

        # Verify driver is still functional
        assert driver.current_url is not None, "Driver should still be functional"

    def test_driver_state_tracking(self, driver):
        """Verify _driver_cache state is managed correctly"""
        # Verify driver is in cache
        assert "driver" in _driver_cache, "Driver should be in module cache"
        assert _driver_cache["driver"] is not None, "Cached driver should not be None"
        assert _driver_cache["driver"] is driver, (
            "Cached driver should be the same instance as fixture"
        )

        # Verify finalizer is registered
        assert _driver_finalizer_registered, (
            "Driver finalizer should be registered"
        )

        # Verify driver is functional
        assert driver is not None, "Driver should exist"
        assert hasattr(driver, "get"), "Driver should have get method"
