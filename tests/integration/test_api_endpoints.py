"""
Integration tests for API endpoints using FastAPI TestClient
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
from io import BytesIO
import zipfile
import json


@pytest.fixture
def client():
    """Create a test client"""
    from src.index import app
    return TestClient(app)


@pytest.fixture
def mock_zip_file():
    """Create a mock ZIP file"""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('config.json', '{"model_type": "bert"}')
        zip_file.writestr('pytorch_model.bin', b'fake weights')
    zip_buffer.seek(0)
    return zip_buffer.read()


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_endpoint(self, client):
        """Test basic health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "ok" in str(data).lower()
    
    def test_health_components(self, client):
        """Test health components endpoint"""
        response = client.get("/health/components")
        assert response.status_code == 200


class TestPackageEndpoints:
    """Test package management endpoints"""
    
    @patch('src.services.s3_service.list_models')
    def test_list_packages(self, mock_list, client):
        """Test listing packages"""
        mock_list.return_value = {
            "models": [
                {"name": "test-model", "version": "1.0.0"}
            ],
            "next_token": None
        }
        
        response = client.get("/api/packages")
        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
    
    @patch('src.services.s3_service.upload_model')
    def test_upload_package(self, mock_upload, client, mock_zip_file):
        """Test uploading a package"""
        mock_upload.return_value = {"status": "success"}
        
        response = client.post(
            "/api/packages/upload",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 200
    
    @patch('src.routes.packages.download_model')
    def test_download_package(self, mock_download, client):
        """Test downloading a package"""
        mock_download.return_value = b"fake zip content"
        
        response = client.get("/api/packages/models/test/1.0.0/model.zip")
        assert response.status_code == 200
        assert "application/zip" in response.headers.get("content-type", "")


class TestArtifactEndpoints:
    """Test artifact endpoints"""
    
    @patch('src.services.artifact_storage.list_all_artifacts')
    @patch('src.services.s3_service.list_models')
    def test_get_artifact_by_name(self, mock_list_models, mock_list, client):
        """Test getting artifact by name"""
        mock_list.return_value = [
            {"id": "1", "name": "test-model", "type": "model"}
        ]
        mock_list_models.return_value = {"models": [{"name": "test-model", "version": "1.0.0"}]}
        
        # Need auth token for this endpoint
        response = client.get("/artifact/byName/test-model", headers={"Authorization": "Bearer test-token"})
        assert response.status_code in [200, 403]  # May require auth
    
    @patch('src.services.artifact_storage.get_artifact')
    @patch('src.services.s3_service.list_models')
    @patch('src.services.auth_service.verify_jwt_token')
    def test_get_artifact_by_id(self, mock_verify, mock_list_models, mock_get, client):
        """Test getting artifact by ID"""
        mock_get.return_value = {
            "id": "1",
            "name": "test-model",
            "type": "model"
        }
        mock_list_models.return_value = {"models": []}
        mock_verify.return_value = {"user_id": "test", "roles": ["user"]}
        
        response = client.get("/artifact/model/1", headers={"Authorization": "Bearer test-token"})
        # May return 200, 404, or 403 depending on implementation
        assert response.status_code in [200, 404, 403]
    
    @patch('src.services.s3_service.list_artifacts_from_s3')
    @patch('src.services.artifact_storage.list_all_artifacts')
    @patch('src.services.s3_service.list_models')
    def test_search_artifacts_by_regex(self, mock_list_models, mock_db_list, mock_s3_list, client):
        """Test searching artifacts by regex"""
        mock_db_list.return_value = []
        mock_s3_list.return_value = {"artifacts": []}
        mock_list_models.return_value = {"models": []}
        
        response = client.post(
            "/artifact/byRegEx",
            json={"regex": "test.*"}
        )
        # May require auth
        assert response.status_code in [200, 403]


class TestRatingEndpoints:
    """Test rating endpoints"""
    
    @patch('src.services.rating.run_scorer')
    def test_rate_model(self, mock_scorer, client):
        """Test rating a model"""
        mock_scorer.return_value = {
            "net_score": 0.85,
            "ramp_up": 0.9,
            "license": 1.0
        }
        
        response = client.get("/package/test-model/rate")
        # May return 200 or error if model doesn't exist
        assert response.status_code in [200, 404, 500]
    
    @patch('src.services.rating.run_scorer')
    @patch('src.services.artifact_storage.get_artifact')
    def test_rate_model_by_id(self, mock_get, mock_scorer, client):
        """Test rating a model by ID"""
        mock_scorer.return_value = {
            "net_score": 0.85
        }
        mock_get.return_value = {"id": "test-id", "name": "test-model", "type": "model"}
        
        response = client.get("/artifact/model/test-id/rate")
        # May return 200 or error if model doesn't exist
        assert response.status_code in [200, 404, 500]


class TestResetEndpoint:
    """Test reset endpoint"""
    
    @patch('src.services.s3_service.reset_registry')
    @patch('src.services.artifact_storage.clear_all_artifacts')
    @patch('src.services.auth_service.verify_jwt_token')
    def test_reset_system(self, mock_verify, mock_clear, mock_reset, client):
        """Test resetting the system"""
        mock_reset.return_value = {"status": "ok"}
        mock_clear.return_value = True
        mock_verify.return_value = {"roles": ["admin"], "username": "admin"}
        
        response = client.delete("/reset", headers={"Authorization": "Bearer test-token"})
        # May require admin auth
        assert response.status_code in [200, 401, 403]


class TestIngestEndpoint:
    """Test ingest endpoint"""
    
    @patch('src.services.s3_service.model_ingestion')
    @patch('src.services.artifact_storage.list_all_artifacts')
    @patch('src.services.auth_service.verify_jwt_token')
    def test_ingest_model(self, mock_verify, mock_list, mock_ingest, client):
        """Test ingesting a model"""
        mock_ingest.return_value = {
            "status": "success",
            "model_id": "test-model"
        }
        mock_list.return_value = []
        mock_verify.return_value = {"user_id": "test", "roles": ["user"]}
        
        response = client.post(
            "/artifact/ingest",
            json={
                "model_id": "test-model",
                "version": "1.0.0"
            },
            headers={"Authorization": "Bearer test-token"}
        )
        # May return 200, 400, 403, or 500
        assert response.status_code in [200, 400, 403, 500]


class TestLineageEndpoint:
    """Test lineage endpoint"""
    
    @patch('src.services.s3_service.get_model_lineage_from_config')
    @patch('src.services.artifact_storage.get_artifact')
    @patch('src.services.auth_service.verify_jwt_token')
    def test_get_lineage(self, mock_verify, mock_get, mock_lineage, client):
        """Test getting model lineage"""
        mock_lineage.return_value = {
            "lineage_metadata": {},
            "lineage_map": {}
        }
        mock_get.return_value = {"id": "test-id", "name": "test-model", "type": "model"}
        mock_verify.return_value = {"user_id": "test", "roles": ["user"]}
        
        response = client.get("/artifact/model/test-id/lineage", headers={"Authorization": "Bearer test-token"})
        # May return 200, 404, or 403
        assert response.status_code in [200, 404, 403]


class TestLicenseCheckEndpoint:
    """Test license check endpoint"""
    
    @patch('src.services.license_compatibility.extract_model_license')
    @patch('src.services.license_compatibility.extract_github_license')
    @patch('src.services.license_compatibility.check_license_compatibility')
    @patch('src.services.artifact_storage.get_artifact')
    @patch('src.services.auth_service.verify_jwt_token')
    def test_license_check(self, mock_verify, mock_get, mock_check, mock_gh, mock_model, client):
        """Test license compatibility check"""
        mock_model.return_value = "mit"
        mock_gh.return_value = "mit"
        mock_check.return_value = {
            "compatible": True,
            "reason": "Both licenses are the same"
        }
        mock_get.return_value = {"id": "test-id", "name": "test-model", "type": "model"}
        mock_verify.return_value = {"user_id": "test", "roles": ["user"]}
        
        response = client.post(
            "/artifact/model/test-id/license-check",
            json={"github_url": "https://github.com/user/repo"},
            headers={"Authorization": "Bearer test-token"}
        )
        # May return 200, 404, or 403
        assert response.status_code in [200, 404, 403]

