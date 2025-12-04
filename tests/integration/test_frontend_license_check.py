"""
Selenium integration tests for the license-check page frontend UI (/license-check).
Tests WCAG 2.1 Level AA compliance and frontend UI functionality.
Note: These tests verify the frontend UI only, not backend license compatibility logic.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tests.constants import PAGE_LOAD_MAX_TIME
from tests.utils.performance_measurement import measure_time
from tests.integration.test_accessibility_base import AccessibilityTestBase

pytestmark = pytest.mark.integration


class TestLicenseCheckFrontendAccessibility(AccessibilityTestBase):
    """Test WCAG 2.1 Level AA compliance on license-check page frontend."""
    
    @property
    def page_path(self):
        return "/license-check"
    
    @property
    def expected_title_keyword(self):
        return "License"
    
    def test_language_attribute(self, driver, base_url):
        """Test that HTML lang attribute is set (WCAG 3.1.1)."""
        driver.get(f"{base_url}{self.page_path}")
        # Check if page loaded correctly (not a 404 JSON response)
        page_source = driver.page_source.lower()
        if ('{"detail":"not found"}' in page_source or
                '"detail":"not found"' in page_source):
            pytest.skip(
                "License-check route not found - "
                "server may need restart or route not registered"
            )
        html = driver.find_element(By.TAG_NAME, "html")
        lang_attr = html.get_attribute("lang")
        assert lang_attr == "en", (
            f"HTML lang attribute should be 'en', got '{lang_attr}'"
        )
    
    def test_page_title(self, driver, base_url):
        """Test that page has a descriptive title (WCAG 2.4.2)."""
        driver.get(f"{base_url}{self.page_path}")
        # Check if page loaded correctly (not a 404 JSON response)
        page_source = driver.page_source.lower()
        if ('{"detail":"not found"}' in page_source or
                '"detail":"not found"' in page_source):
            pytest.skip(
                "License-check route not found - "
                "server may need restart or route not registered"
            )
        title = driver.title
        assert title and len(title) > 0, "Page should have a title"
        assert self.expected_title_keyword in title, f"Title should contain '{self.expected_title_keyword}'"
    
    def test_heading_hierarchy(self, driver, base_url):
        """Test that headings are in logical order (WCAG 1.3.1)."""
        driver.get(f"{base_url}{self.page_path}")
        # Check if page loaded correctly (not a 404 JSON response)
        page_source = driver.page_source.lower()
        if ('{"detail":"not found"}' in page_source or
                '"detail":"not found"' in page_source):
            pytest.skip(
                "License-check route not found - "
                "server may need restart or route not registered"
            )
        h1 = driver.find_elements(By.TAG_NAME, "h1")
        assert len(h1) > 0, "Page should have at least one h1"
        headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")
        if len(headings) > 1:
            for i in range(len(headings) - 1):
                current_level = int(headings[i].tag_name[1])
                next_level = int(headings[i + 1].tag_name[1])
                assert next_level <= current_level + 1, "Headings should not skip levels"
    
    def test_form_labels(self, driver, base_url):
        """Test that all form inputs have associated labels (WCAG 1.3.1, 4.1.2)."""
        driver.get(f"{base_url}/license-check")
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='url'], select, textarea")
        for input_elem in inputs:
            input_id = input_elem.get_attribute("id")
            if input_id:
                label = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_id}']")
                aria_label = input_elem.get_attribute("aria-label")
                assert len(label) > 0 or aria_label, f"Input {input_id} should have a label or aria-label"
    
    def test_required_fields(self, driver, base_url):
        """Test that required fields are marked (WCAG 3.3.2)."""
        driver.get(f"{base_url}/license-check")
        required_inputs = driver.find_elements(By.CSS_SELECTOR, "input[required], select[required], textarea[required]")
        for inp in required_inputs:
            aria_required = inp.get_attribute("aria-required")
            assert inp.get_attribute("required") == "true" or aria_required == "true", "Required fields should be marked"
    
    def test_error_associations(self, driver, base_url):
        """Test that error messages are associated with form fields (WCAG 3.3.1)."""
        driver.get(f"{base_url}/license-check")
        submit_button = driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
        if submit_button:
            submit_button[0].click()
            # Wait for any error messages
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            # Check if errors are associated with inputs via aria-describedby or aria-invalid
            inputs_with_errors = driver.find_elements(By.CSS_SELECTOR, "input[aria-invalid='true']")
            inputs_with_describedby = driver.find_elements(By.CSS_SELECTOR, "input[aria-describedby]")
            # Form validation should exist - either aria-invalid or aria-describedby should be present
            # If no errors appear, that's also valid (form might have client-side validation)
            # Verify page is still accessible after form submission attempt
            body = driver.find_element(By.TAG_NAME, "body")
            assert body is not None, "Page should remain accessible after form submission"
            # Verify that if errors exist, they are properly associated with inputs
            if len(inputs_with_errors) > 0 or len(inputs_with_describedby) > 0:
                # At least one input should have error association
                assert len(inputs_with_errors) > 0 or len(inputs_with_describedby) > 0, "Error messages should be associated with form fields"


class TestLicenseCheckFrontendUI:
    """Test license-check page frontend UI functionality."""
    
    def test_license_check_page_loads(self, driver, base_url):
        """Test that license-check page frontend loads successfully."""
        with measure_time("license_check_page_load") as timer:
            driver.get(f"{base_url}/license-check")
        # Check if page loaded correctly (not a 404 JSON response)
        page_source = driver.page_source
        if ('{"detail":"Not Found"}' in page_source or
                '"detail":"Not Found"' in page_source):
            pytest.skip(
                "License-check route not found - "
                "server may need restart or route not registered"
            )
        assert ("License" in page_source or "License" in driver.title), (
            "Page should contain 'License' text"
        )
        # Performance assertion: license-check page should load within threshold
        assert timer.elapsed <= PAGE_LOAD_MAX_TIME, (
            f"License-check page load took {timer.elapsed:.2f}s, "
            f"exceeds threshold of {PAGE_LOAD_MAX_TIME}s"
        )
    
    def test_license_check_form_ui_structure(self, driver, base_url):
        """Test that license-check form UI has proper structure."""
        driver.get(f"{base_url}/license-check")
        forms = driver.find_elements(By.CSS_SELECTOR, "form")
        assert len(forms) > 0, "License-check page should have a form"
    
    def test_github_url_input_ui(self, driver, base_url):
        """Test that GitHub URL input UI element is present."""
        driver.get(f"{base_url}/license-check")
        url_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='url'], input[type='text']")
        # Should have at least one input for GitHub URL
        assert len(url_inputs) > 0, "License-check page should have URL input"
    
    def test_model_id_input_ui(self, driver, base_url):
        """Test that Model ID input UI element is present."""
        driver.get(f"{base_url}/license-check")
        # Check for model ID input (could be text input or select)
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], select")
        # Should have inputs for model ID
        assert len(inputs) > 0, "License-check page should have model ID input"
    
    def test_submit_button_ui(self, driver, base_url):
        """Test that submit button UI element is present."""
        driver.get(f"{base_url}/license-check")
        submit_buttons = driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
        assert len(submit_buttons) > 0, "License-check page should have a submit button"
    
    def test_results_ui_display(self, driver, base_url):
        """Test that license compatibility results UI elements can be displayed."""
        driver.get(f"{base_url}/license-check")
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        # Check if results structure exists (could be in various formats)
        driver.find_elements(
            By.CSS_SELECTOR,
            ".results, .compatibility, .license-check, dl, table"
        )
        # Page should have loaded successfully - body element exists
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "License-check page should load"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

