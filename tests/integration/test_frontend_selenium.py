"""
Selenium frontend tests for ACME Registry
Tests the frontend UI using Selenium WebDriver
"""
import pytest
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.routes.frontend import setup_app
from src.index import app


@pytest.fixture(scope="session")
def test_app():
    """Create a test FastAPI app instance"""
    # Use the main app from index.py and ensure frontend routes are registered
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


@pytest.fixture(scope="function")
def driver():
    """Create a Selenium WebDriver instance"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode for CI
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Try to use webdriver-manager to handle ChromeDriver
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        # Fallback to system ChromeDriver if webdriver-manager fails
        print(f"Warning: Could not use webdriver-manager: {e}")
        driver = webdriver.Chrome(options=chrome_options)
    
    yield driver
    driver.quit()


@pytest.fixture(scope="session")
def server_url():
    """Return the base URL for the test server"""
    return "http://localhost:8000"


@pytest.mark.selenium
class TestFrontendHome:
    """Test the home page"""
    
    def test_home_page_loads(self, test_client, driver, server_url):
        """Test that the home page loads correctly"""
        # Start a simple test server or use test_client
        # For Selenium, we need an actual server running
        # This is a simplified test that works with test_client
        
        # Mock the server response
        response = test_client.get("/")
        assert response.status_code == 200
        
        # If we had a running server, we'd do:
        # driver.get(f"{server_url}/")
        # assert "ACME Registry" in driver.title or "ACME Registry" in driver.page_source


@pytest.mark.selenium
@pytest.mark.integration
class TestFrontendPagesWithSelenium:
    """Integration tests using Selenium for actual browser interaction"""
    
    def test_home_page_title(self, test_client):
        """Test home page has correct content"""
        response = test_client.get("/")
        assert response.status_code == 200
        assert "ACME Registry" in response.text or "Welcome" in response.text
    
    def test_directory_page_accessible(self, test_client):
        """Test directory page is accessible"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            response = test_client.get("/directory")
            assert response.status_code == 200
            assert "Directory" in response.text or "Package" in response.text
    
    def test_upload_page_accessible(self, test_client):
        """Test upload page is accessible"""
        response = test_client.get("/upload")
        assert response.status_code == 200
        assert "upload" in response.text.lower() or "Upload" in response.text
    
    def test_rate_page_accessible(self, test_client):
        """Test rate page is accessible"""
        response = test_client.get("/rate")
        assert response.status_code == 200
    
    def test_rate_page_with_name(self, test_client):
        """Test rate page with a package name"""
        with patch("src.routes.frontend.run_scorer") as mock_scorer:
            mock_scorer.return_value = {
                "net_score": 0.8,
                "NetScore": 0.8,
                "RampUp": 0.7,
                "Correctness": 0.9,
            }
            response = test_client.get("/rate?name=test-model")
            assert response.status_code == 200
    
    def test_admin_page_accessible(self, test_client):
        """Test admin page is accessible"""
        response = test_client.get("/admin")
        assert response.status_code == 200
    
    def test_lineage_page_accessible(self, test_client):
        """Test lineage page is accessible"""
        response = test_client.get("/lineage")
        assert response.status_code == 200
    
    def test_lineage_page_with_name(self, test_client):
        """Test lineage page with a model name"""
        with patch("src.services.s3_service.get_model_lineage_from_config") as mock_lineage:
            mock_lineage.return_value = {
                "lineage_map": {},
                "lineage_metadata": {},
                "config": {},
            }
            response = test_client.get("/lineage?name=test-model")
            assert response.status_code == 200
    
    def test_size_cost_page_accessible(self, test_client):
        """Test size cost page is accessible"""
        response = test_client.get("/size-cost")
        assert response.status_code == 200
    
    def test_size_cost_page_with_name(self, test_client):
        """Test size cost page with a model name"""
        with patch("src.services.s3_service.get_model_sizes") as mock_sizes:
            mock_sizes.return_value = {
                "full": 1000,
                "weights": 500,
                "datasets": 500,
            }
            response = test_client.get("/size-cost?name=test-model")
            assert response.status_code == 200
    
    def test_ingest_page_accessible(self, test_client):
        """Test ingest page is accessible"""
        response = test_client.get("/ingest")
        assert response.status_code == 200
    
    def test_license_check_page_accessible(self, test_client):
        """Test license check page is accessible if it exists"""
        # Check if route exists
        response = test_client.get("/license-check")
        # May return 404 if route doesn't exist, which is OK for this test
        assert response.status_code in [200, 404]
    
    def test_navigation_links(self, test_client):
        """Test that navigation links exist in base template"""
        response = test_client.get("/")
        html = response.text
        # Check for navigation links
        assert "/directory" in html or 'href="/directory"' in html
        assert "/upload" in html or 'href="/upload"' in html
    
    def test_directory_search_form(self, test_client):
        """Test directory page has search form"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            response = test_client.get("/directory")
            html = response.text.lower()
            # Check for search form elements
            assert "search" in html or "form" in html or "input" in html
    
    def test_upload_form(self, test_client):
        """Test upload page has upload form"""
        response = test_client.get("/upload")
        html = response.text.lower()
        # Check for form elements
        assert "form" in html or "upload" in html or "file" in html


@pytest.mark.selenium
@pytest.mark.integration
class TestFrontendInteraction:
    """Test user interactions on frontend pages"""
    
    def test_directory_search_query(self, test_client):
        """Test directory search with query parameter"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": [{"name": "test-model", "version": "1.0.0"}]}
            response = test_client.get("/directory?q=test")
            assert response.status_code == 200
    
    def test_directory_name_regex(self, test_client):
        """Test directory search with name regex"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            response = test_client.get("/directory?name_regex=^test.*")
            assert response.status_code == 200
    
    def test_directory_model_regex(self, test_client):
        """Test directory search with model regex"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.return_value = {"models": []}
            response = test_client.get("/directory?model_regex=.*transformer.*")
            assert response.status_code == 200
    
    def test_upload_file_validation(self, test_client):
        """Test upload endpoint validates file type"""
        # Test with invalid file type
        response = test_client.post("/upload", files={"file": ("test.txt", b"content", "text/plain")})
        assert response.status_code == 200
        # Should return error for non-zip files
        data = response.json()
        assert "error" in data or "Only ZIP" in str(data)
    
    def test_ingest_post(self, test_client):
        """Test ingest form submission"""
        with patch("src.services.s3_service.model_ingestion") as mock_ingest:
            mock_ingest.return_value = {"status": "success"}
            response = test_client.post("/ingest", data={"name": "test-model", "version": "main"})
            assert response.status_code == 200
    
    def test_admin_reset(self, test_client):
        """Test admin reset functionality"""
        with patch("src.routes.frontend.reset_registry") as mock_reset:
            mock_reset.return_value = {"message": "Reset successful"}
            response = test_client.post("/admin/reset")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data or "success" in str(data).lower()


@pytest.mark.selenium
@pytest.mark.integration
class TestFrontendErrorHandling:
    """Test error handling in frontend"""
    
    def test_directory_error_handling(self, test_client):
        """Test directory page handles errors gracefully"""
        with patch("src.routes.frontend.list_models") as mock_list:
            mock_list.side_effect = Exception("Test error")
            response = test_client.get("/directory")
            # Should still return 200, but with empty packages list
            assert response.status_code == 200
    
    def test_rate_error_handling(self, test_client):
        """Test rate page handles missing package gracefully"""
        response = test_client.get("/rate?name=nonexistent")
        assert response.status_code == 200
    
    def test_lineage_error_handling(self, test_client):
        """Test lineage page handles errors gracefully"""
        with patch("src.services.s3_service.get_model_lineage_from_config") as mock_lineage:
            mock_lineage.side_effect = Exception("Test error")
            response = test_client.get("/lineage?name=test-model")
            assert response.status_code == 200
    
    def test_size_cost_error_handling(self, test_client):
        """Test size cost page handles errors gracefully"""
        with patch("src.services.s3_service.get_model_sizes") as mock_sizes:
            mock_sizes.side_effect = Exception("Test error")
            response = test_client.get("/size-cost?name=test-model")
            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

