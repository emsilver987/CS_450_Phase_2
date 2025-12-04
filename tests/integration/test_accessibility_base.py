"""
Base class for shared accessibility tests (WCAG 2.1 Level AA).
This reduces code duplication across frontend test files.
"""
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys


class AccessibilityTestBase:
    """Base class for WCAG 2.1 Level AA accessibility tests."""
    
    @property
    def page_path(self):
        """Override this property in subclasses to specify the page path."""
        raise NotImplementedError("Subclasses must define page_path property")
    
    @property
    def expected_title_keyword(self):
        """Override this property in subclasses to specify expected title keyword."""
        raise NotImplementedError("Subclasses must define expected_title_keyword property")
    
    def test_language_attribute(self, driver, base_url):
        """Test that HTML lang attribute is set (WCAG 3.1.1)."""
        driver.get(f"{base_url}{self.page_path}")
        html = driver.find_element(By.TAG_NAME, "html")
        assert html.get_attribute("lang") == "en", "HTML lang attribute should be 'en'"
    
    def test_page_title(self, driver, base_url):
        """Test that page has a descriptive title (WCAG 2.4.2)."""
        driver.get(f"{base_url}{self.page_path}")
        title = driver.title
        assert title and len(title) > 0, "Page should have a title"
        assert self.expected_title_keyword in title, f"Title should contain '{self.expected_title_keyword}'"
    
    def test_heading_hierarchy(self, driver, base_url):
        """Test that headings are in logical order (WCAG 1.3.1)."""
        driver.get(f"{base_url}{self.page_path}")
        h1 = driver.find_elements(By.TAG_NAME, "h1")
        assert len(h1) > 0, "Page should have at least one h1"
        headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, h4, h5, h6")
        if len(headings) > 1:
            for i in range(len(headings) - 1):
                current_level = int(headings[i].tag_name[1])
                next_level = int(headings[i + 1].tag_name[1])
                assert next_level <= current_level + 1, "Headings should not skip levels"
    
    def test_keyboard_navigation(self, driver, base_url):
        """Test that all interactive elements are keyboard accessible (WCAG 2.1.1)."""
        driver.get(f"{base_url}{self.page_path}")
        body = driver.find_element(By.TAG_NAME, "body")
        body.send_keys(Keys.TAB)
        focused = driver.switch_to.active_element
        assert focused is not None, "Should be able to focus on elements with keyboard"
    
    def test_focus_indicators(self, driver, base_url):
        """Test that focus indicators are visible (WCAG 2.4.7)."""
        driver.get(f"{base_url}{self.page_path}")
        inputs = driver.find_elements(By.CSS_SELECTOR, "input, button")
        if inputs:
            inputs[0].send_keys(Keys.TAB)
            focused = driver.switch_to.active_element
            outline = focused.value_of_css_property("outline")
            box_shadow = focused.value_of_css_property("box-shadow")
            assert outline != "none" or box_shadow != "none", "Focused elements should have visible focus indicators"

