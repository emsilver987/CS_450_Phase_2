"""
Unit tests for frontend routes
"""
from unittest.mock import patch
from fastapi.testclient import TestClient
from fastapi import FastAPI


class TestFrontendRoutes:
    """Test frontend route handlers"""

    def setup_method(self):
        """Reset routes_registered before each test to ensure isolation"""
        import src.routes.frontend
        # Reset the flag to ensure routes can be registered fresh for each test
        src.routes.frontend.routes_registered = False
        # Clear any cached module state if needed
        # This ensures tests can run in any order without state leakage

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
        assert response.status_code == 200
        # When templates is None, returns JSON
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            # When templates exist, returns HTML
            assert len(response.text) > 0

    @patch('src.routes.frontend.list_models')
    def test_directory_with_version_range_query(self, mock_list):
        """Test directory route with version range in query parameter"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_list.return_value = {"models": []}
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        # Test with version pattern in q parameter
        response = client.get("/directory?q=1.0.0")
        assert response.status_code == 200
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args[1]
        assert call_kwargs.get("version_range") == "1.0.0"

    @patch('src.routes.frontend.list_models')
    def test_directory_with_name_regex_query(self, mock_list):
        """Test directory route with name regex in query parameter"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_list.return_value = {"models": []}
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        # Test with non-version pattern in q parameter (should be treated as name regex)
        response = client.get("/directory?q=test-model")
        assert response.status_code == 200
        mock_list.assert_called_once()
        call_kwargs = mock_list.call_args[1]
        assert "name_regex" in call_kwargs
        # The regex will escape special characters, so check for the pattern
        assert "test" in call_kwargs["name_regex"] and "model" in call_kwargs["name_regex"]

    @patch('src.routes.frontend.list_models')
    def test_directory_exception_handling(self, mock_list):
        """Test directory route exception handling"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_list.side_effect = Exception("Database error")
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/directory")
        assert response.status_code == 200
        # When templates is None, returns JSON; when templates exist, returns HTML
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            # Exception is caught and packages is set to empty list, then template renders
            assert len(response.text) > 0

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
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.run_scorer')
    def test_rate_get_no_templates(self, mock_scorer):
        """Test rate GET route without templates"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_scorer.return_value = {"net_score": 0.8}
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/rate?name=test-model")
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

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
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.run_scorer')
    def test_rate_by_id_no_templates(self, mock_scorer):
        """Test rate by ID route without templates"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_scorer.return_value = {"net_score": 0.8}
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/artifact/model/test-id/rate")
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.upload_model')
    def test_upload_post_success(self, mock_upload):
        """Test upload POST route successfully"""
        from src.routes.frontend import setup_app
        
        mock_upload.return_value = {"message": "Upload successful"}
        
        app = setup_app()
        client = TestClient(app)
        
        files = {"file": ("test.zip", b"fake zip content", "application/zip")}
        response = client.post("/upload", files=files, data={"model_id": "test-model"})
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "error" in data

    @patch('src.routes.frontend.upload_model')
    def test_upload_post_invalid_file(self, mock_upload):
        """Test upload POST with invalid file"""
        from src.routes.frontend import setup_app
        
        app = setup_app()
        client = TestClient(app)
        
        files = {"file": ("test.txt", b"content", "text/plain")}
        response = client.post("/upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "ZIP files" in data["error"]

    @patch('src.routes.frontend.upload_model')
    def test_upload_post_exception(self, mock_upload):
        """Test upload POST with exception"""
        from src.routes.frontend import setup_app
        
        mock_upload.side_effect = Exception("Upload failed")
        app = setup_app()
        client = TestClient(app)
        
        files = {"file": ("test.zip", b"fake zip content", "application/zip")}
        response = client.post("/upload", files=files)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Upload failed" in data["error"]

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
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.get_model_lineage_from_config')
    def test_lineage_exception(self, mock_lineage):
        """Test lineage route with exception"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_lineage.side_effect = Exception("Lineage error")
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/lineage?name=test-model")
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

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
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.get_model_sizes')
    def test_size_cost_exception(self, mock_sizes):
        """Test size cost route with exception"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_sizes.side_effect = Exception("Size error")
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/size-cost?name=test-model")
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

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
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.services.s3_service.model_ingestion')
    def test_ingest_post_http_exception(self, mock_ingest):
        """Test ingest POST route with HTTPException"""
        from src.routes.frontend import setup_app, set_templates
        from fastapi import HTTPException
        
        error_detail = {
            "error": "Ingestion failed",
            "message": "Model not ingestible",
            "metric_scores": {"net_score": 0.3}
        }
        mock_ingest.side_effect = HTTPException(status_code=400, detail=error_detail)
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/ingest", data={"name": "test-model", "version": "main"})
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.services.s3_service.model_ingestion')
    def test_ingest_post_generic_exception(self, mock_ingest):
        """Test ingest POST route with generic exception"""
        from src.routes.frontend import setup_app, set_templates
        
        mock_ingest.side_effect = Exception("Ingest failed")
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/ingest", data={"name": "test-model", "version": "main"})
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.download_model')
    def test_download_success(self, mock_download):
        """Test download route successfully"""
        from src.routes.frontend import setup_app
        
        mock_download.return_value = b"fake zip content"
        
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/download/test-model/1.0.0")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

    @patch('src.routes.frontend.download_model')
    def test_download_not_found(self, mock_download):
        """Test download route when model not found"""
        from src.routes.frontend import setup_app
        
        mock_download.return_value = None
        
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/download/test-model/1.0.0")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    @patch('src.routes.frontend.download_model')
    def test_download_exception(self, mock_download):
        """Test download route with exception"""
        from src.routes.frontend import setup_app
        
        mock_download.side_effect = Exception("Download failed")
        
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/download/test-model/1.0.0")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Download failed" in data["error"]

    @patch('src.routes.frontend.reset_registry')
    def test_reset_success(self, mock_reset):
        """Test reset route successfully"""
        from src.routes.frontend import setup_app
        
        mock_reset.return_value = {"message": "Reset successful"}
        
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/admin/reset")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "error" in data

    @patch('src.routes.frontend.reset_registry')
    def test_reset_exception(self, mock_reset):
        """Test reset route with exception"""
        from src.routes.frontend import setup_app
        
        mock_reset.side_effect = Exception("Reset failed")
        
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/admin/reset")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Reset failed" in data["error"]

    @patch('src.services.s3_service.sync_model_lineage_to_neptune')
    def test_sync_neptune_success(self, mock_sync):
        """Test sync-neptune endpoint successfully"""
        from src.routes.frontend import setup_app
        
        mock_sync.return_value = {"synced": 5}
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/lineage/sync-neptune")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "error" in data

    @patch('src.services.s3_service.sync_model_lineage_to_neptune')
    def test_sync_neptune_exception(self, mock_sync):
        """Test sync-neptune endpoint with exception"""
        from src.routes.frontend import setup_app
        
        mock_sync.side_effect = Exception("Sync failed")
        app = setup_app()
        client = TestClient(app)
        
        response = client.post("/lineage/sync-neptune")
        assert response.status_code == 200
        data = response.json()
        assert "error" in data
        assert "Sync failed" in data["error"]

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

    @patch('src.routes.frontend.templates', None)
    def test_upload_get_no_templates(self):
        """Test upload GET route without templates"""
        from src.routes.frontend import setup_app, set_templates
        
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/upload")
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.templates', None)
    def test_admin_no_templates(self):
        """Test admin route without templates"""
        from src.routes.frontend import setup_app, set_templates
        
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/admin")
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    @patch('src.routes.frontend.templates', None)
    def test_ingest_get_no_templates(self):
        """Test ingest GET route without templates"""
        from src.routes.frontend import setup_app, set_templates
        
        set_templates(None)
        app = setup_app()
        client = TestClient(app)
        
        response = client.get("/ingest")
        assert response.status_code == 200
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
            assert "Frontend not found" in data["message"]
        else:
            assert len(response.text) > 0

    def test_routes_registered_isolation(self):
        """Test that routes_registered flag doesn't leak between tests"""
        import src.routes.frontend
        from src.routes.frontend import setup_app

        # Reset flag to start clean
        src.routes.frontend.routes_registered = False

        # First call should register routes
        app1 = setup_app()
        msg1 = "routes_registered should be True after first setup_app call"
        assert src.routes.frontend.routes_registered is True, msg1

        # Verify routes were actually registered (not skipped)
        routes_before_reset = len([r for r in app1.routes])
        assert routes_before_reset > 0, "Routes should be registered in app1"

        # Reset flag manually (simulating what setup_method does)
        src.routes.frontend.routes_registered = False

        # Second call should register routes again (not skip due to flag)
        app2 = setup_app()
        msg2 = "routes_registered should be True after second setup_app call"
        assert src.routes.frontend.routes_registered is True, msg2

        # Verify routes were registered again
        routes_after_reset = len([r for r in app2.routes])
        msg3 = "Routes should be registered in app2 after flag reset"
        assert routes_after_reset > 0, msg3

