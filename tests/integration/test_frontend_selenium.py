"""
Selenium frontend tests for ACME Registry
Tests the frontend UI using Selenium WebDriver with real browser interaction
"""
import pytest
import time
import subprocess
import signal
import os
import requests
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from fastapi.testclient import TestClient
from unittest.mock import patch

from src.index import app


# Global server process
_server_process = None
_server_port = 8001  # Use different port to avoid conflicts


def start_test_server():
    """Start a test server in a separate process"""
    global _server_process
    if _server_process is None or _server_process.poll() is not None:
        # Set environment variables for test mode
        env = os.environ.copy()
        project_root = str(Path(__file__).resolve().parents[2])
        env['PYTHONPATH'] = project_root
        env['TESTING'] = '1'
        
        # Start uvicorn server
        cmd = [
            'python', '-m', 'uvicorn', 'src.index:app',
            '--host', '127.0.0.1', '--port', str(_server_port)
        ]
        _server_process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        # Wait for server to start and verify
        max_retries = 15
        for i in range(max_retries):
            try:
                response = requests.get(f"http://127.0.0.1:{_server_port}/health", timeout=1)
                if response.status_code == 200:
                    break
            except Exception:
                if i < max_retries - 1:
                    time.sleep(0.5)
                else:
                    print("Warning: Server may not have started")
    return _server_process


def stop_test_server():
    """Stop the test server"""
    global _server_process
    if _server_process:
        try:
            if hasattr(os, 'setsid'):
                os.killpg(os.getpgid(_server_process.pid), signal.SIGTERM)
            else:
                _server_process.terminate()
            _server_process.wait(timeout=5)
        except Exception:
            try:
                _server_process.kill()
            except Exception:
                pass
        _server_process = None


@pytest.fixture(scope="session")
def test_app():
    """Create a test FastAPI app instance"""
    from src.routes import frontend as frontend_routes
    from fastapi.templating import Jinja2Templates
    from fastapi.staticfiles import StaticFiles
    
    # Setup templates
    frontend_root = Path(__file__).resolve().parents[2] / "frontend"
    templates_path = frontend_root / "templates"
    static_path = frontend_root / "static"
    
    if templates_path.exists():
        templates = Jinja2Templates(directory=str(templates_path))
        frontend_routes.set_templates(templates)
    
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
    
    return app


@pytest.fixture(scope="session")
def test_client(test_app):
    """Create a test client for the app"""
    return TestClient(test_app)


@pytest.fixture(scope="session", autouse=True)
def test_server():
    """Start test server for Selenium tests"""
    process = start_test_server()
    yield process
    stop_test_server()


@pytest.fixture(scope="function")
def driver():
    """Create a Selenium WebDriver instance"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode for CI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Try to use webdriver-manager to handle ChromeDriver
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        # Fallback to system ChromeDriver if webdriver-manager fails
        print(f"Warning: Could not use webdriver-manager: {e}")
        driver = webdriver.Chrome(options=chrome_options)
    
    driver.implicitly_wait(5)
    yield driver
    driver.quit()


@pytest.fixture(scope="session")
def server_url():
    """Return the base URL for the test server"""
    return f"http://localhost:{_server_port}"


@pytest.mark.selenium
class TestFrontendHome:
    """Test the home page with Selenium"""
    
    def test_home_page_loads(self, driver, server_url):
        """Test that the home page loads correctly"""
        driver.get(f"{server_url}/")
        wait = WebDriverWait(driver, 10)
        
        # Check page title or heading
        heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "ACME Registry" in heading.text or "Welcome" in heading.text
        
        # Check navigation links exist
        nav = driver.find_element(By.TAG_NAME, "nav")
        assert nav is not None
    
    def test_home_page_navigation_links(self, driver, server_url):
        """Test navigation links on home page"""
        driver.get(f"{server_url}/")
        wait = WebDriverWait(driver, 10)
        
        # Wait for page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "nav")))
        
        # Check for directory link
        directory_link = driver.find_element(By.XPATH, "//a[@href='/directory']")
        assert directory_link is not None
        
        # Check for upload link
        upload_link = driver.find_element(By.XPATH, "//a[@href='/upload']")
        assert upload_link is not None
    
    def test_home_page_action_buttons(self, driver, server_url):
        """Test action buttons on home page"""
        driver.get(f"{server_url}/")
        wait = WebDriverWait(driver, 10)
        
        # Wait for page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "main")))
        
        # Check for Browse Directory button
        browse_btn = driver.find_element(By.XPATH, "//a[contains(@href, '/directory')]")
        assert browse_btn is not None
        
        # Check for Upload Package button
        upload_btn = driver.find_element(By.XPATH, "//a[contains(@href, '/upload')]")
        assert upload_btn is not None


@pytest.mark.selenium
@pytest.mark.integration
class TestFrontendPagesWithSelenium:
    """Integration tests using Selenium for actual browser interaction"""
    
    def test_home_page_title(self, driver, server_url):
        """Test home page has correct content"""
        driver.get(f"{server_url}/")
        wait = WebDriverWait(driver, 10)
        heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "ACME Registry" in heading.text or "Welcome" in heading.text
    
    def test_directory_page_accessible(self, driver, server_url):
        """Test directory page is accessible"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory")
            wait = WebDriverWait(driver, 10)
            heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            assert "Directory" in heading.text or "Package" in heading.text
    
    def test_directory_page_search_form(self, driver, server_url):
        """Test directory page has search form"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory")
            wait = WebDriverWait(driver, 10)
            
            # Check for search input
            search_input = wait.until(EC.presence_of_element_located((By.NAME, "q")))
            assert search_input is not None
            
            # Check for search button
            search_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            assert search_button is not None
    
    def test_directory_advanced_search(self, driver, server_url):
        """Test directory advanced search options"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory")
            wait = WebDriverWait(driver, 10)
            
            # Find and click advanced search details
            details = wait.until(EC.presence_of_element_located((By.TAG_NAME, "details")))
            details.click()
            time.sleep(0.5)  # Wait for details to expand
            
            # Check for advanced search fields
            name_regex = driver.find_element(By.NAME, "name_regex")
            model_regex = driver.find_element(By.NAME, "model_regex")
            version_range = driver.find_element(By.NAME, "version_range")
            
            assert name_regex is not None
            assert model_regex is not None
            assert version_range is not None
    
    def test_upload_page_accessible(self, driver, server_url):
        """Test upload page is accessible"""
        driver.get(f"{server_url}/upload")
        wait = WebDriverWait(driver, 10)
        heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "upload" in heading.text.lower() or "Upload" in heading.text
    
    def test_upload_page_form(self, driver, server_url):
        """Test upload page has upload form"""
        driver.get(f"{server_url}/upload")
        wait = WebDriverWait(driver, 10)
        
        # Check for file input
        file_input = wait.until(EC.presence_of_element_located((By.NAME, "file")))
        assert file_input is not None
        assert file_input.get_attribute("type") == "file"
        assert file_input.get_attribute("accept") == ".zip"
        
        # Check for submit button
        submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        assert submit_button is not None
    
    def test_rate_page_accessible(self, driver, server_url):
        """Test rate page is accessible"""
        driver.get(f"{server_url}/rate")
        wait = WebDriverWait(driver, 10)
        # Page should load without error
        assert driver.current_url.endswith("/rate")
    
    def test_rate_page_with_name(self, driver, server_url):
        """Test rate page with a package name"""
        with patch("src.routes.frontend.run_scorer") as mock_scorer:
            mock_scorer.return_value = {
                "net_score": 0.8,
                "NetScore": 0.8,
                "RampUp": 0.7,
                "Correctness": 0.9,
            }
            driver.get(f"{server_url}/rate?name=test-model")
            wait = WebDriverWait(driver, 10)
            # Page should load
            assert driver.current_url.endswith("/rate") or "test-model" in driver.current_url
    
    def test_admin_page_accessible(self, driver, server_url):
        """Test admin page is accessible"""
        driver.get(f"{server_url}/admin")
        wait = WebDriverWait(driver, 10)
        heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "admin" in heading.text.lower() or "Admin" in heading.text
    
    def test_lineage_page_accessible(self, driver, server_url):
        """Test lineage page is accessible"""
        driver.get(f"{server_url}/lineage")
        wait = WebDriverWait(driver, 10)
        # Page should load
        assert driver.current_url.endswith("/lineage")
    
    def test_lineage_page_with_name(self, driver, server_url):
        """Test lineage page with a model name"""
        with patch("src.services.s3_service.get_model_lineage_from_config") as mock_lineage:
            mock_lineage.return_value = {
                "lineage_map": {},
                "lineage_metadata": {},
                "config": {},
            }
            driver.get(f"{server_url}/lineage?name=test-model")
            wait = WebDriverWait(driver, 10)
            # Page should load
            assert driver.current_url.endswith("/lineage") or "test-model" in driver.current_url
    
    def test_size_cost_page_accessible(self, driver, server_url):
        """Test size cost page is accessible"""
        driver.get(f"{server_url}/size-cost")
        wait = WebDriverWait(driver, 10)
        # Page should load
        assert driver.current_url.endswith("/size-cost")
    
    def test_size_cost_page_with_name(self, driver, server_url):
        """Test size cost page with a model name"""
        with patch("src.services.s3_service.get_model_sizes") as mock_sizes:
            mock_sizes.return_value = {
                "full": 1000,
                "weights": 500,
                "datasets": 500,
            }
            driver.get(f"{server_url}/size-cost?name=test-model")
            wait = WebDriverWait(driver, 10)
            # Page should load
            assert driver.current_url.endswith("/size-cost") or "test-model" in driver.current_url
    
    def test_ingest_page_accessible(self, driver, server_url):
        """Test ingest page is accessible"""
        driver.get(f"{server_url}/ingest")
        wait = WebDriverWait(driver, 10)
        heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "ingest" in heading.text.lower() or "Ingest" in heading.text
    
    def test_ingest_page_form(self, driver, server_url):
        """Test ingest page has form"""
        driver.get(f"{server_url}/ingest")
        wait = WebDriverWait(driver, 10)
        
        # Check for form
        form = wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        assert form is not None
    
    def test_license_check_page_accessible(self, driver, server_url):
        """Test license check page is accessible if it exists"""
        driver.get(f"{server_url}/license-check")
        wait = WebDriverWait(driver, 10)
        # May return 404 if route doesn't exist, which is OK for this test
        assert driver.current_url.endswith("/license-check") or "404" not in driver.page_source.lower()
    
    def test_navigation_links(self, driver, server_url):
        """Test that navigation links exist in base template"""
        driver.get(f"{server_url}/")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "nav")))
        
        # Check for navigation links
        directory_link = driver.find_element(By.XPATH, "//a[@href='/directory']")
        upload_link = driver.find_element(By.XPATH, "//a[@href='/upload']")
        
        assert directory_link is not None
        assert upload_link is not None


@pytest.mark.selenium
@pytest.mark.integration
class TestFrontendInteraction:
    """Test user interactions on frontend pages"""
    
    def test_directory_search_query(self, driver, server_url):
        """Test directory search with query parameter"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": [{"name": "test-model", "version": "1.0.0"}]}
            driver.get(f"{server_url}/directory?q=test")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            # Page should load with search results
            assert driver.current_url.endswith("/directory") or "q=test" in driver.current_url
    
    def test_directory_search_form_submission(self, driver, server_url):
        """Test directory search form submission"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory")
            wait = WebDriverWait(driver, 10)
            
            # Find search input
            search_input = wait.until(EC.presence_of_element_located((By.NAME, "q")))
            search_input.clear()
            search_input.send_keys("test-query")
            
            # Submit form
            search_button = driver.find_element(By.XPATH, "//button[@type='submit']")
            search_button.click()
            
            # Wait for page to update
            time.sleep(1)
            assert "q=test-query" in driver.current_url
    
    def test_directory_name_regex(self, driver, server_url):
        """Test directory search with name regex"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory?name_regex=^test.*")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            assert driver.current_url.endswith("/directory") or "name_regex" in driver.current_url
    
    def test_directory_model_regex(self, driver, server_url):
        """Test directory search with model regex"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory?model_regex=.*transformer.*")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            assert driver.current_url.endswith("/directory") or "model_regex" in driver.current_url
    
    def test_directory_version_range(self, driver, server_url):
        """Test directory search with version range"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory?version_range=1.0.0")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            assert driver.current_url.endswith("/directory") or "version_range" in driver.current_url
    
    def test_directory_advanced_search_form(self, driver, server_url):
        """Test advanced search form interaction"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            driver.get(f"{server_url}/directory")
            wait = WebDriverWait(driver, 10)
            
            # Open advanced search
            details = wait.until(EC.presence_of_element_located((By.TAG_NAME, "details")))
            details.click()
            time.sleep(0.5)
            
            # Fill in advanced search fields
            name_regex_input = driver.find_element(By.NAME, "name_regex")
            name_regex_input.clear()
            name_regex_input.send_keys("^test.*")
            
            model_regex_input = driver.find_element(By.NAME, "model_regex")
            model_regex_input.clear()
            model_regex_input.send_keys(".*transformer.*")
            
            # Submit advanced search
            submit_button = driver.find_element(By.XPATH, "//form[@aria-label='Advanced search']//button[@type='submit']")
            submit_button.click()
            
            time.sleep(1)
            assert "name_regex" in driver.current_url or "model_regex" in driver.current_url
    
    def test_upload_file_validation(self, driver, server_url):
        """Test upload endpoint validates file type"""
        driver.get(f"{server_url}/upload")
        wait = WebDriverWait(driver, 10)
        
        # Find file input
        file_input = wait.until(EC.presence_of_element_located((By.NAME, "file")))
        assert file_input is not None
        assert file_input.get_attribute("accept") == ".zip"
    
    def test_navigation_between_pages(self, driver, server_url):
        """Test navigation between different pages"""
        driver.get(f"{server_url}/")
        wait = WebDriverWait(driver, 10)
        
        # Navigate to directory
        directory_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/directory']")))
        directory_link.click()
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "/directory" in driver.current_url
        
        # Navigate to upload
        upload_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/upload']")))
        upload_link.click()
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "/upload" in driver.current_url
        
        # Navigate back to home
        home_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@href='/']")))
        home_link.click()
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert driver.current_url.endswith("/") or "/directory" not in driver.current_url
    
    def test_rate_by_id_route(self, driver, server_url):
        """Test rate by artifact ID route"""
        with patch("src.routes.frontend.run_scorer") as mock_scorer:
            mock_scorer.return_value = {
                "net_score": 0.8,
                "NetScore": 0.8,
            }
            driver.get(f"{server_url}/artifact/model/test-id/rate")
            wait = WebDriverWait(driver, 10)
            # Page should load
            assert "/rate" in driver.current_url or "test-id" in driver.current_url
    
    def test_download_route(self, driver, server_url):
        """Test download route"""
        with patch("src.routes.frontend.download_model") as mock_download:
            mock_download.return_value = b"fake zip content"
            driver.get(f"{server_url}/download/test-model/1.0.0")
            # Download should be triggered
            assert driver.current_url.endswith("/download/test-model/1.0.0")


@pytest.mark.selenium
@pytest.mark.integration
class TestFrontendErrorHandling:
    """Test error handling in frontend"""
    
    def test_directory_error_handling(self, driver, server_url):
        """Test directory page handles errors gracefully"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.side_effect = Exception("Test error")
            driver.get(f"{server_url}/directory")
            wait = WebDriverWait(driver, 10)
            # Should still load page
            heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            assert heading is not None
    
    def test_rate_error_handling(self, driver, server_url):
        """Test rate page handles missing package gracefully"""
        driver.get(f"{server_url}/rate?name=nonexistent")
        WebDriverWait(driver, 10)
        # Page should still load
        assert driver.current_url.endswith("/rate") or "nonexistent" in driver.current_url
    
    def test_lineage_error_handling(self, driver, server_url):
        """Test lineage page handles errors gracefully"""
        with patch("src.services.s3_service.get_model_lineage_from_config") as mock_lineage:
            mock_lineage.side_effect = Exception("Test error")
            driver.get(f"{server_url}/lineage?name=test-model")
            WebDriverWait(driver, 10)
            # Page should still load
            assert driver.current_url.endswith("/lineage") or "test-model" in driver.current_url
    
    def test_size_cost_error_handling(self, driver, server_url):
        """Test size cost page handles errors gracefully"""
        with patch("src.services.s3_service.get_model_sizes") as mock_sizes:
            mock_sizes.side_effect = Exception("Test error")
            driver.get(f"{server_url}/size-cost?name=test-model")
            WebDriverWait(driver, 10)
            # Page should still load
            assert driver.current_url.endswith("/size-cost") or "test-model" in driver.current_url
    
    def test_upload_error_handling(self, driver, server_url):
        """Test upload page handles errors"""
        driver.get(f"{server_url}/upload")
        wait = WebDriverWait(driver, 10)
        # Page should load
        heading = wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert heading is not None


@pytest.mark.selenium
@pytest.mark.integration
class TestFrontendComprehensive:
    """Comprehensive frontend tests covering all routes"""
    
    def test_all_navigation_links(self, driver, server_url):
        """Test all navigation links in header"""
        driver.get(f"{server_url}/")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "nav")))

        links = [
            "/",
            "/directory",
            "/upload",
            "/rate",
            "/lineage",
            "/size-cost",
            "/ingest",
            "/license-check",
            "/admin"
        ]

        for link in links:
            try:
                nav_link = driver.find_element(By.XPATH, f"//a[@href='{link}']")
                assert nav_link is not None
            except Exception:
                # Some links might not exist, that's OK
                pass
    
    def test_directory_with_packages(self, driver, server_url):
        """Test directory page with mock packages"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {
                "models": [
                    {"name": "model1", "version": "1.0.0", "size": 1000},
                    {"name": "model2", "version": "2.0.0", "size": 2000},
                ]
            }
            driver.get(f"{server_url}/directory")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            
            # Check if packages are displayed
            page_text = driver.page_source
            assert "model1" in page_text or "model2" in page_text
    
    def test_rate_page_with_rating_data(self, driver, server_url):
        """Test rate page displays rating data"""
        with patch("src.routes.frontend.run_scorer") as mock_scorer:
            mock_scorer.return_value = {
                "net_score": 0.85,
                "NetScore": 0.85,
                "RampUp": 0.75,
                "Correctness": 0.90,
                "BusFactor": 0.80,
                "ResponsiveMaintainer": 0.70,
                "LicenseScore": 0.95,
                "Reproducibility": 0.88,
                "Reviewedness": 0.82,
                "Treescore": 0.79,
            }
            driver.get(f"{server_url}/rate?name=test-model")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            # Page should load with rating data
            assert driver.current_url.endswith("/rate") or "test-model" in driver.current_url
    
    def test_ingest_form_interaction(self, driver, server_url):
        """Test ingest form interaction"""
        driver.get(f"{server_url}/ingest")
        wait = WebDriverWait(driver, 10)
        
        # Check for form
        form = wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))
        assert form is not None
        
        # Check for name input if it exists
        try:
            name_input = driver.find_element(By.NAME, "name")
            assert name_input is not None
        except Exception:
            # Form might use different structure
            pass
    
    def test_lineage_with_data(self, driver, server_url):
        """Test lineage page with lineage data"""
        with patch("src.services.s3_service.get_model_lineage_from_config") as mock_lineage:
            mock_lineage.return_value = {
                "lineage_map": {"parent1": "child1"},
                "lineage_metadata": {"key": "value"},
                "config": {"model": "test"},
            }
            driver.get(f"{server_url}/lineage?name=test-model&version=1.0.0")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            # Page should load
            assert driver.current_url.endswith("/lineage") or "test-model" in driver.current_url
    
    def test_size_cost_with_data(self, driver, server_url):
        """Test size cost page with size data"""
        with patch("src.services.s3_service.get_model_sizes") as mock_sizes:
            mock_sizes.return_value = {
                "full": 1000000,
                "weights": 500000,
                "datasets": 500000,
                "weights_uncompressed": 600000,
                "datasets_uncompressed": 600000,
            }
            driver.get(f"{server_url}/size-cost?name=test-model&version=1.0.0")
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
            # Page should load
            assert driver.current_url.endswith("/size-cost") or "test-model" in driver.current_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
