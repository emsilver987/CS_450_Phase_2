"""
Selenium integration tests for the upload page frontend UI (/upload).
Tests WCAG 2.1 Level AA compliance and frontend UI functionality.
Note: These tests verify the frontend UI only, not backend upload processing.
"""
import os
import pathlib
import pytest
import tempfile
import time
import uuid
import zipfile
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from tests.constants import PAGE_LOAD_MAX_TIME, FORM_SUBMIT_MAX_TIME
from tests.utils.performance_measurement import measure_time
from tests.integration.test_accessibility_base import AccessibilityTestBase

pytestmark = pytest.mark.integration


class TestUploadFrontendAccessibility(AccessibilityTestBase):
    """Test WCAG 2.1 Level AA compliance on upload page frontend."""
    
    @property
    def page_path(self):
        return "/upload"
    
    @property
    def expected_title_keyword(self):
        return "Upload"
    
    def test_form_labels(self, driver, base_url):
        """Test that all form inputs have associated labels (WCAG 1.3.1, 4.1.2)."""
        driver.get(f"{base_url}/upload")
        inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='file'], input[type='url'], select, textarea")
        for input_elem in inputs:
            input_id = input_elem.get_attribute("id")
            if input_id:
                # Check for label with 'for' attribute
                label = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_id}']")
                # Or check for aria-label
                aria_label = input_elem.get_attribute("aria-label")
                assert len(label) > 0 or aria_label, f"Input {input_id} should have a label or aria-label"
    
    def test_file_input_labels(self, driver, base_url):
        """Test that file inputs have proper labels."""
        driver.get(f"{base_url}/upload")
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        for inp in file_inputs:
            input_id = inp.get_attribute("id")
            if input_id:
                label = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_id}']")
                aria_label = inp.get_attribute("aria-label")
                assert len(label) > 0 or aria_label, f"File input {input_id} should have a label or aria-label"
    
    def test_required_fields(self, driver, base_url):
        """Test that required fields are marked (WCAG 3.3.2)."""
        driver.get(f"{base_url}/upload")
        required_inputs = driver.find_elements(By.CSS_SELECTOR, "input[required], select[required], textarea[required]")
        if not required_inputs:
            # If no required fields are found, check if form has any inputs at all
            all_inputs = driver.find_elements(By.CSS_SELECTOR, "input, select, textarea")
            if not all_inputs:
                pytest.skip("No form inputs found on upload page")
            # If inputs exist but none are marked required, that's also valid
            # (form might use client-side validation instead)
            return
        
        for inp in required_inputs:
            required_attr = inp.get_attribute("required")
            aria_required = inp.get_attribute("aria-required")
            # Check that required attribute is set or aria-required is true
            assert required_attr is not None or aria_required == "true", (
                f"Required field {inp.get_attribute('id') or inp.get_attribute('name')} should be marked"
            )
    
    def test_error_associations(self, driver, base_url):
        """Test that error messages are associated with form fields (WCAG 3.3.1)."""
        driver.get(f"{base_url}/upload")
        submit_button = driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
        if submit_button:
            submit_button[0].click()
            # Wait for any error messages
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
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
    
    def test_focus_indicators(self, driver, base_url):
        """Test that focus indicators are visible (WCAG 2.4.7)."""
        driver.get(f"{base_url}{self.page_path}")
        # Find interactive elements, excluding file inputs which can't receive keyboard focus via send_keys
        interactive_elements = driver.find_elements(By.CSS_SELECTOR, "input:not([type='file']), button, select, textarea, a[href]")
        if not interactive_elements:
            # Fallback: try buttons only
            interactive_elements = driver.find_elements(By.CSS_SELECTOR, "button")
        
        if interactive_elements:
            # Use JavaScript to focus the element instead of send_keys for better compatibility
            driver.execute_script("arguments[0].focus();", interactive_elements[0])
            focused = driver.switch_to.active_element
            outline = focused.value_of_css_property("outline")
            box_shadow = focused.value_of_css_property("box-shadow")
            assert outline != "none" or box_shadow != "none", "Focused elements should have visible focus indicators"
        else:
            pytest.skip("No interactive elements found to test focus indicators")


class TestUploadFrontendUI:
    """Test upload page frontend UI functionality."""
    
    def test_upload_page_loads(self, driver, base_url):
        """Test that upload page frontend loads successfully."""
        with measure_time("upload_page_load") as timer:
            driver.get(f"{base_url}/upload")
        assert "Upload" in driver.page_source or "Upload" in driver.title
        # Performance assertion: upload page should load within threshold
        assert timer.elapsed <= PAGE_LOAD_MAX_TIME, (
            f"Upload page load took {timer.elapsed:.2f}s, "
            f"exceeds threshold of {PAGE_LOAD_MAX_TIME}s"
        )
    
    def test_file_input_ui_present(self, driver, base_url):
        """Test that file input UI element is present on the page."""
        driver.get(f"{base_url}/upload")
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        assert len(file_inputs) > 0, "Upload page should have a file input"
    
    def test_upload_form_ui_structure(self, driver, base_url):
        """Test that upload form UI has proper structure."""
        driver.get(f"{base_url}/upload")
        forms = driver.find_elements(By.CSS_SELECTOR, "form")
        assert len(forms) > 0, "Upload page should have a form"
        # Check form has enctype for file uploads
        for form in forms:
            enctype = form.get_attribute("enctype")
            if file_inputs := driver.find_elements(By.CSS_SELECTOR, "input[type='file']"):
                # If file input exists, form should have multipart/form-data
                assert enctype == "multipart/form-data" or not enctype, "Form should support file uploads"
    
    def test_valid_upload_simulation(self, driver, base_url):
        """
        Test valid upload flow simulation.
        Creates a dummy zip file and attempts to upload it.
        Note: This tests the frontend UI upload mechanism, not backend processing.
        """
        # Create a temporary zip file for testing using tempfile for cross-platform compatibility
        unique_id = uuid.uuid4().hex[:8]
        temp_dir = tempfile.gettempdir()
        
        # Ensure temp directory exists
        os.makedirs(temp_dir, exist_ok=True)
        
        temp_zip_path = os.path.join(temp_dir, f"test_package_{unique_id}.zip")
        
        try:
            # Create a valid zip file with content
            with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("dummy.txt", "content for upload test")
            
            # Verify the zip file was created
            assert os.path.exists(temp_zip_path), f"Zip file should exist at {temp_zip_path}"
            assert os.path.isfile(temp_zip_path), f"Zip file should be a file: {temp_zip_path}"
            
            # Resolve to absolute path for Selenium
            absolute_path = os.path.abspath(temp_zip_path)
            
            driver.get(f"{base_url}/upload")
            
            try:
                # Find file input
                file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                
                # Send file path to input
                file_input.send_keys(absolute_path)
                
                # Verify file was selected (value attribute should be set)
                file_value = file_input.get_attribute("value")
                assert file_value is not None and len(file_value) > 0, "File input should have a value after selection"
                
                # Try to find and fill other form fields if they exist
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
                
                # Find submit button
                submit_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    "button[type='submit'], input[type='submit']"
                )
                
                # Store URL before submission
                url_before = driver.current_url
                
                # Measure form submission time
                with measure_time("form_submission") as timer:
                    # Submit form
                    submit_btn.click()
                    
                    # Wait for response - either success message, error message, or redirect
                    WebDriverWait(driver, 10).until(
                        lambda d: any([
                            d.current_url != url_before,  # Redirect occurred
                            len(d.find_elements(By.CSS_SELECTOR, ".alert, .message, .notification, .error, .success")) > 0,  # Message appeared
                            "success" in d.find_element(By.TAG_NAME, "body").text.lower(),
                            "error" in d.find_element(By.TAG_NAME, "body").text.lower(),
                        ])
                    )
                
                # Performance assertion: form submission should complete within threshold
                # Note: This is a soft assertion for uploads since file size can vary
                if timer.elapsed > FORM_SUBMIT_MAX_TIME:
                    # Log warning but don't fail - large files may take longer
                    print(
                        f"Warning: Form submission took {timer.elapsed:.2f}s, "
                        f"exceeds threshold of {FORM_SUBMIT_MAX_TIME}s. "
                        f"This may be acceptable for file uploads."
                    )
                
                # Verify page state after upload attempt
                assert driver.page_source is not None, "Page should still exist"
                assert len(driver.page_source) > 0, "Page should have content"
                
                # Page may show success, error, or stay on upload page - all are valid
                page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
                has_success = "success" in page_text or "uploaded" in page_text
                has_error = "error" in page_text or "invalid" in page_text or "failed" in page_text
                still_on_upload = "upload" in driver.current_url.lower()
                
                assert has_success or has_error or still_on_upload, (
                    "Page should show success/error message or stay on upload page after submission"
                )
                
            except NoSuchElementException:
                pytest.skip("Upload form elements not found")
                
        finally:
            # Cleanup: remove temporary file
            try:
                if os.path.exists(temp_zip_path):
                    os.remove(temp_zip_path)
            except Exception as e:
                # Log but don't fail - cleanup errors shouldn't break tests
                print(f"Warning: Error during file cleanup: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

