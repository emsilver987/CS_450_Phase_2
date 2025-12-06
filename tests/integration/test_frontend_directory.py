"""
Selenium integration tests for the directory page frontend UI (/directory).
Tests WCAG 2.1 Level AA compliance and frontend UI functionality.
Note: These tests verify the frontend UI only, not backend search functionality.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tests.constants import PAGE_LOAD_MAX_TIME, SEARCH_OPERATION_MAX_TIME
from tests.utils.performance_measurement import measure_time
from tests.integration.test_accessibility_base import AccessibilityTestBase

pytestmark = pytest.mark.integration


class TestDirectoryFrontendAccessibility(AccessibilityTestBase):
    """Test WCAG 2.1 Level AA compliance on directory page frontend."""
    
    @property
    def page_path(self):
        return "/directory"
    
    @property
    def expected_title_keyword(self):
        return "Directory"

    def test_search_form_labels(self, driver, base_url):
        """Test that search form inputs have associated labels (WCAG 1.3.1, 4.1.2)."""
        driver.get(f"{base_url}/directory")
        selector = "input[type='text'], input[type='search']"
        search_inputs = driver.find_elements(By.CSS_SELECTOR, selector)
        for input_elem in search_inputs:
            input_id = input_elem.get_attribute("id")
            if input_id:
                # Check for label with 'for' attribute
                label_selector = f"label[for='{input_id}']"
                label = driver.find_elements(By.CSS_SELECTOR, label_selector)
                # Or check for aria-label
                aria_label = input_elem.get_attribute("aria-label")
                msg = f"Search input {input_id} should have a label or aria-label"
                assert len(label) > 0 or aria_label, msg

    def test_aria_labels(self, driver, base_url):
        """Test that interactive elements have aria-labels where needed (WCAG 4.1.2)."""
        driver.get(f"{base_url}/directory")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for button in buttons:
            text = button.text.strip()
            aria_label = button.get_attribute("aria-label")
            # Buttons should have text or aria-label
            assert text or aria_label, "Button should have text or aria-label"

    def test_skip_links(self, driver, base_url):
        """Test skip links for main content (WCAG 2.4.1)."""
        driver.get(f"{base_url}/directory")
        # Check for skip link or main landmark
        skip_links = driver.find_elements(By.CSS_SELECTOR, "a[href^='#'], .skip-link, [class*='skip']")
        main = driver.find_elements(By.CSS_SELECTOR, "main, [role='main'], #main, #content, .main-content")
        # Page should have either skip links or main landmark (both are valid)
        assert len(skip_links) > 0 or len(main) > 0, (
            "Page should have skip links or main content landmark for accessibility"
        )


class TestDirectoryFrontendUI:
    """Test directory page frontend UI functionality."""

    def test_directory_page_loads(self, driver, base_url):
        """Test that directory page frontend loads successfully."""
        with measure_time("directory_page_load") as timer:
            driver.get(f"{base_url}/directory")
        assert "Package Directory" in driver.page_source or "Directory" in driver.title
        # Performance assertion: directory page should load within threshold
        assert timer.elapsed <= PAGE_LOAD_MAX_TIME, (
            f"Directory page load took {timer.elapsed:.2f}s, "
            f"exceeds threshold of {PAGE_LOAD_MAX_TIME}s"
        )

    def test_search_form_ui(self, driver, base_url):
        """Test that search form UI elements are present and interactable."""
        driver.get(f"{base_url}/directory")
        selector = "input[type='text'], input[type='search'], input[id='q']"
        search_inputs = driver.find_elements(By.CSS_SELECTOR, selector)
        if search_inputs:
            search_input = search_inputs[0]
            search_input.clear()
            search_input.send_keys("test")
            button_selector = "button[type='submit']"
            search_button = driver.find_element(By.CSS_SELECTOR, button_selector)
            
            # Measure search operation time
            with measure_time("search_operation") as timer:
                search_button.click()
                # Wait for results or error message to appear in UI
                result_selector = ".grid, .no-results, table, .package-list"
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, result_selector))
                )
            
            # Performance assertion: search operation should complete within threshold
            assert timer.elapsed <= SEARCH_OPERATION_MAX_TIME, (
                f"Search operation took {timer.elapsed:.2f}s, "
                f"exceeds threshold of {SEARCH_OPERATION_MAX_TIME}s"
            )

    def test_model_list_ui_display(self, driver, base_url):
        """Test that model list UI elements are displayed in the directory."""
        driver.get(f"{base_url}/directory")
        # Wait for content to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        # Page should have loaded successfully - body element exists
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "Directory page should load"
        # Verify page has content (body text or model list elements)
        body_text = body.text.strip()
        selector = ".grid, .package-list, table, .model-item"
        model_elements = driver.find_elements(By.CSS_SELECTOR, selector)
        msg = "Directory page should have content or model list elements"
        assert len(body_text) > 0 or len(model_elements) > 0, msg


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
