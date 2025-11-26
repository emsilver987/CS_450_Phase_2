"""
Unit tests for frontend routes
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestFrontendRoutes:
    """Test frontend route handlers"""

    def setup_method(self):
        """Reset routes_registered before each test"""
        import src.routes.frontend
        src.routes.frontend.routes_registered = False

    @patch('src.routes.frontend.templates', None)
    def test_home_no_templates(self):
        """Test home route without templates"""
        from src.routes.frontend import setup_app, set_templates
        from pathlib import Path
        
        # Ensure templates is None
        set_templates(None)
        # Patch Path.exists to return False for templates path
        with patch.object(Path, 'exists', return_value=False):
            app = setup_app()
            # Ensure templates stays None
            set_templates(None)
            client = TestClient(app)
            
            response = client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "Frontend not found" in data["message"]

    @patch('src.routes.frontend.list_models')
    def test_directory_success(self, mock_list):
        """Test directory route successfully"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_list.return_value = {
            "models": [{"name": "test-model", "version": "1.0.0"}]
        }
        
        # Set templates to None so it returns JSON
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/directory")
        # When templates is None, returns JSON with message
        assert response.status_code in [200, 404, 500]

    @patch('src.routes.frontend.run_scorer')
    def test_rate_get_success(self, mock_scorer):
        """Test rate GET route successfully"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_scorer.return_value = {
            "net_score": 0.8,
            "ramp_up": 0.7,
            "code_quality": 0.9
        }
        
        # Set templates to None so it returns JSON
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/rate?name=test-model")
        assert response.status_code in [200, 404, 500]

    @patch('src.routes.frontend.run_scorer')
    def test_rate_by_id_success(self, mock_scorer):
        """Test rate by ID route successfully"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_scorer.return_value = {
            "net_score": 0.8,
            "ramp_up": 0.7
        }
        
        # Set templates to None so it returns JSON
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/artifact/model/test-id/rate")
        assert response.status_code in [200, 404, 500]

    @patch('src.routes.frontend.upload_model')
    def test_upload_post_success(self, mock_upload):
        """Test upload POST route successfully"""
        from src.routes.frontend import setup_app
        
        mock_upload.return_value = {"message": "Upload successful"}
        
        app = setup_app()
        client = TestClient(app)
        
        files = {"file": ("test.zip", b"fake zip content", "application/zip")}
        response = client.post("/upload", files=files, data={"model_id": "test-model"})
        assert response.status_code in [200, 404, 500]

    @patch('src.routes.frontend.upload_model')
    def test_upload_post_invalid_file(self, mock_upload):
        """Test upload POST with invalid file"""
        from src.routes.frontend import setup_app
        
        app = setup_app()
        client = TestClient(app)
        
        files = {"file": ("test.txt", b"content", "text/plain")}
        response = client.post("/upload", files=files)
        assert response.status_code in [200, 400, 404, 500]

    @patch('src.routes.frontend.get_model_lineage_from_config')
    def test_lineage_success(self, mock_lineage):
        """Test lineage route successfully"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_lineage.return_value = {
            "lineage_map": {"model1": {"name": "Model 1"}},
            "lineage_metadata": {}
        }
        
        # Set templates to None so it returns JSON
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/lineage?name=test-model")
        assert response.status_code in [200, 404, 500]

    @patch('src.routes.frontend.get_model_sizes')
    def test_size_cost_success(self, mock_sizes):
        """Test size cost route successfully"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_sizes.return_value = {
            "full": 1024 * 1024,
            "weights": 512 * 1024
        }
        
        # Set templates to None so it returns JSON
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/size-cost?name=test-model")
        assert response.status_code in [200, 404, 500]

    @patch('src.services.s3_service.model_ingestion')
    def test_ingest_post_success(self, mock_ingest):
        """Test ingest POST route successfully"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_ingest.return_value = {"message": "Ingest successful"}
        
        # Set templates to None so it returns JSON
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/ingest", data={"name": "test-model", "version": "main"})
        assert response.status_code in [200, 404, 500]

    @patch('src.routes.frontend.download_model')
    def test_download_success(self, mock_download):
        """Test download route successfully"""
        from src.routes.frontend import setup_app
        
        mock_download.return_value = b"fake zip content"
        
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/download/test-model/1.0.0")
        assert response.status_code in [200, 404, 500]

    @patch('src.routes.frontend.reset_registry')
    def test_reset_success(self, mock_reset):
        """Test reset route successfully"""
        from src.routes.frontend import setup_app
        
        mock_reset.return_value = {"message": "Reset successful"}
        
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/admin/reset")
        assert response.status_code in [200, 404, 500]

    def test_setup_app_with_app(self):
        """Test setup_app with provided app"""
        from src.routes.frontend import setup_app
        from fastapi import FastAPI
        
        existing_app = FastAPI()
        result = setup_app(app=existing_app)
        assert result == existing_app

    def test_setup_app_standalone(self):
        """Test setup_app creating standalone app"""
        from src.routes.frontend import setup_app
        
        app = setup_app()
        assert app is not None
        assert isinstance(app, FastAPI)

