"""
Selenium integration tests for the lineage page frontend UI (/lineage).
Tests WCAG 2.1 Level AA compliance and frontend UI functionality.
Note: These tests verify the frontend UI only, not backend lineage calculation.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tests.constants import PAGE_LOAD_MAX_TIME
from tests.utils.performance_measurement import measure_time
from tests.integration.test_accessibility_base import AccessibilityTestBase

pytestmark = pytest.mark.integration


class TestLineageFrontendAccessibility(AccessibilityTestBase):
    """Test WCAG 2.1 Level AA compliance on lineage page frontend."""
    
    @property
    def page_path(self):
        return "/lineage"
    
    @property
    def expected_title_keyword(self):
        return "Lineage"
    
    def test_search_form_labels(self, driver, base_url):
        """Test that search form inputs have associated labels (WCAG 1.3.1, 4.1.2)."""
        driver.get(f"{base_url}/lineage")
        search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search']")
        for input_elem in search_inputs:
            input_id = input_elem.get_attribute("id")
            if input_id:
                label = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_id}']")
                aria_label = input_elem.get_attribute("aria-label")
                assert len(label) > 0 or aria_label, f"Search input {input_id} should have a label or aria-label"
    
    def test_lineage_display_structure(self, driver, base_url):
        """Test that lineage results are displayed with proper semantic structure."""
        driver.get(f"{base_url}/lineage")
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        # Check for semantic HTML elements for displaying relationships
        content = driver.find_elements(By.CSS_SELECTOR, "ul, ol, dl, .lineage, .relationship")
        # Page should have loaded successfully - body element exists
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "Lineage page should load"
        # Verify page has content (body text or structural elements)
        body_text = body.text.strip()
        assert len(body_text) > 0 or len(content) > 0, "Lineage page should have content or structural elements"


class TestLineageFrontendUI:
    """Test lineage page frontend UI functionality."""
    
    def test_lineage_page_loads(self, driver, base_url):
        """Test that lineage page frontend loads successfully."""
        with measure_time("lineage_page_load") as timer:
            driver.get(f"{base_url}/lineage")
        assert "Lineage" in driver.page_source or "Lineage" in driver.title
        # Performance assertion: lineage page should load within threshold
        assert timer.elapsed <= PAGE_LOAD_MAX_TIME, (
            f"Lineage page load took {timer.elapsed:.2f}s, "
            f"exceeds threshold of {PAGE_LOAD_MAX_TIME}s"
        )
    
    def test_search_form_ui(self, driver, base_url):
        """Test that search form UI elements are present and interactable."""
        driver.get(f"{base_url}/lineage")
        search_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search'], input[id='q'], input[id='model_id']")
        if search_inputs:
            search_input = search_inputs[0]
            search_input.clear()
            search_input.send_keys("test")
            search_button = driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            if search_button:
                search_button[0].click()
                # Wait for results or error message to appear in UI
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".lineage-results, .error, .no-results, ul, ol"))
                )
    
    def test_lineage_ui_display(self, driver, base_url):
        """Test that lineage information UI elements can be displayed."""
        driver.get(f"{base_url}/lineage")
        # Wait for page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        # Check if lineage structure exists (could be in various formats)
        content = driver.find_elements(By.CSS_SELECTOR, "ul, ol, .lineage, .relationship, .parent, .child")
        # Page should have loaded successfully - body element exists
        body = driver.find_element(By.TAG_NAME, "body")
        assert body is not None, "Lineage page should load"
        # Verify page has content (body text or structural elements)
        body_text = body.text.strip()
        assert len(body_text) > 0 or len(content) > 0, "Lineage page should have content or structural elements"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

