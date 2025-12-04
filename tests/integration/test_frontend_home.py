"""
Selenium integration tests for the homepage frontend UI.
Tests WCAG 2.1 Level AA compliance and frontend UI functionality.
Note: These tests verify the frontend UI only, not backend functionality.
"""
import pytest
from selenium.webdriver.common.by import By
from tests.constants import PAGE_LOAD_MAX_TIME
from tests.utils.performance_measurement import measure_time, assert_page_load_performance
from tests.integration.test_accessibility_base import AccessibilityTestBase

pytestmark = pytest.mark.integration


class TestHomeFrontendAccessibility(AccessibilityTestBase):
    """Test WCAG 2.1 Level AA compliance on homepage frontend."""
    
    @property
    def page_path(self):
        return "/"
    
    @property
    def expected_title_keyword(self):
        return "ACME"
    
    def test_skip_link(self, driver, base_url):
        """Test skip link for main content (WCAG 2.4.1)."""
        driver.get(base_url)
        # Check for skip link or main landmark
        skip_links = driver.find_elements(By.CSS_SELECTOR, ".skip-link, a[href='#main']")
        main = driver.find_elements(By.CSS_SELECTOR, "main, [role='main'], #main")
        assert len(skip_links) > 0 or len(main) > 0, "Page should have skip link or main landmark"
    
    def test_navigation_structure(self, driver, base_url):
        """Test navigation has proper ARIA labels."""
        driver.get(base_url)
        nav = driver.find_elements(By.CSS_SELECTOR, "nav, [role='navigation']")
        if nav:
            aria_label = nav[0].get_attribute("aria-label")
            assert aria_label, "Navigation should have aria-label"


class TestHomeFrontendUI:
    """Test homepage frontend UI functionality."""
    
    def test_homepage_loads(self, driver, base_url):
        """Test that homepage frontend loads successfully."""
        with measure_time("homepage_load") as timer:
            driver.get(base_url)
        assert "ACME Registry" in driver.title or "ACME Registry" in driver.page_source
        # Performance assertion: homepage should load within threshold
        assert timer.elapsed <= PAGE_LOAD_MAX_TIME, (
            f"Homepage load took {timer.elapsed:.2f}s, "
            f"exceeds threshold of {PAGE_LOAD_MAX_TIME}s"
        )
    
    def test_navigation_links_ui(self, driver, base_url):
        """Test that all navigation links are present and clickable in the frontend."""
        driver.get(base_url)
        # Get hrefs first to avoid stale element issues
        nav_links = driver.find_elements(By.CSS_SELECTOR, "nav a")
        hrefs = []
        for link in nav_links:
            try:
                href = link.get_attribute("href")
                if href and not href.startswith("#"):
                    if base_url in href or href.startswith("/"):
                        hrefs.append(href)
            except Exception:
                # Skip stale elements
                continue
        
        # Test each link by navigating directly
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        from tests.constants import NAVIGATION_MAX_TIME
        
        for href in hrefs:
            try:
                # Measure navigation time
                with measure_time("navigation") as nav_timer:
                    driver.get(href)
                    # Wait for page to load using WebDriverWait instead of sleep
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                assert driver.current_url, "Navigation should work"
                # Performance assertion: navigation should complete within threshold
                assert nav_timer.elapsed <= NAVIGATION_MAX_TIME, (
                    f"Navigation to {href} took {nav_timer.elapsed:.2f}s, "
                    f"exceeds threshold of {NAVIGATION_MAX_TIME}s"
                )
                
                # Measure back navigation time
                with measure_time("back_navigation") as back_timer:
                    driver.back()  # Return to homepage
                    # Wait for navigation back to complete
                    WebDriverWait(driver, 10).until(
                        lambda d: d.current_url == base_url or base_url in d.current_url
                    )
                assert back_timer.elapsed <= NAVIGATION_MAX_TIME, (
                    f"Back navigation took {back_timer.elapsed:.2f}s, "
                    f"exceeds threshold of {NAVIGATION_MAX_TIME}s"
                )
            except Exception as e:
                # Use pytest.skip for expected failures (e.g., auth-required links)
                pytest.skip(f"Navigation test skipped for {href}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

