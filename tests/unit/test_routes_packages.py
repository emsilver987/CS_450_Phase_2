"""
Unit tests for packages routes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from io import BytesIO
import zipfile


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


class TestPackagesRoutes:
    """Test package management routes"""

    @patch('src.routes.packages.list_models')
    def test_list_packages_success(self, mock_list_models, client):
        """Test listing packages successfully"""
        mock_list_models.return_value = {
            "models": [
                {"name": "test-model", "version": "1.0.0"}
            ],
            "next_token": None
        }

        response = client.get("/api/packages")
        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert len(data["packages"]) == 1

    @patch('src.routes.packages.list_models')
    def test_list_packages_with_filters(self, mock_list_models, client):
        """Test listing packages with filters"""
        mock_list_models.return_value = {"models": [], "next_token": None}

        response = client.get(
            "/api/packages",
            params={"name_regex": "test.*", "limit": 50}
        )
        assert response.status_code == 200
        mock_list_models.assert_called_once()

    @patch('src.routes.packages.list_models')
    def test_search_packages(self, mock_list_models, client):
        """Test searching packages"""
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "1.0.0"}],
            "next_token": None
        }

        response = client.get("/api/packages/search", params={"q": "test"})
        assert response.status_code == 200
        data = response.json()
        assert "packages" in data

    @patch('src.routes.packages.upload_model')
    def test_upload_package_success(self, mock_upload, client, mock_zip_file):
        """Test uploading a package successfully"""
        mock_upload.return_value = {"status": "success", "model_id": "test-model"}

        response = client.post(
            "/api/packages/upload",
            files={"file": ("test.zip", mock_zip_file, "application/zip")},
            params={"debloat": False}
        )
        assert response.status_code == 200

    def test_upload_package_invalid_file(self, client):
        """Test uploading a non-ZIP file"""
        response = client.post(
            "/api/packages/upload",
            files={"file": ("test.txt", b"not a zip", "text/plain")}
        )
        assert response.status_code == 400

    @patch('src.routes.packages.download_model')
    def test_download_model_success(self, mock_download, client):
        """Test downloading a model successfully"""
        mock_download.return_value = b"fake zip content"

        response = client.get(
            "/api/packages/models/test-model/1.0.0/model.zip",
            params={"component": "full"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

    @patch('src.routes.packages.download_model')
    def test_download_model_not_found(self, mock_download, client):
        """Test downloading a non-existent model"""
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_download.side_effect = ClientError(error_response, "GetObject")

        response = client.get("/api/packages/models/nonexistent/1.0.0/model.zip")
        assert response.status_code == 404

    @patch('src.routes.packages.reset_registry')
    def test_reset_system(self, mock_reset, client):
        """Test resetting the system"""
        mock_reset.return_value = {"status": "ok"}

        response = client.post("/api/packages/reset")
        assert response.status_code == 200

    @patch('src.services.rating.run_scorer')
    def test_rate_package(self, mock_scorer, client):
        """Test rating a package"""
        mock_scorer.return_value = {
            "net_score": 0.85,
            "ramp_up": 0.9,
            "license": 1.0
        }

        response = client.get("/api/packages/rate/test-model")
        assert response.status_code == 200
        data = response.json()
        assert "net_score" in data or "ramp_up" in data
    
    @patch('src.routes.packages.list_models')
    def test_search_model_cards(self, mock_list_models, client):
        """Test searching model cards"""
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "1.0.0"}],
            "next_token": None
        }
        
        response = client.get("/api/packages/search/model-cards", params={"q": "test"})
        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        mock_list_models.assert_called_once()
    
    @patch('src.routes.packages.list_models')
    def test_advanced_search(self, mock_list_models, client):
        """Test advanced search with multiple filters"""
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "1.0.0"}],
            "next_token": None
        }
        
        response = client.get(
            "/api/packages/search/advanced",
            params={
                "name_regex": "test.*",
                "model_regex": ".*test.*",
                "version_range": "1.0.0",
                "limit": 50
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        mock_list_models.assert_called_once()
    
    @patch('src.routes.packages.list_models')
    def test_advanced_search_minimal_params(self, mock_list_models, client):
        """Test advanced search with minimal parameters"""
        mock_list_models.return_value = {"models": [], "next_token": None}
        
        response = client.get("/api/packages/search/advanced", params={"limit": 10})
        assert response.status_code == 200
        mock_list_models.assert_called_once()
    
    @patch('src.routes.packages.upload_model')
    def test_upload_model_file(self, mock_upload, client, mock_zip_file):
        """Test uploading model file via POST /models/{id}/{version}/model.zip"""
        mock_upload.return_value = {"status": "success", "model_id": "test-model"}
        
        response = client.post(
            "/api/packages/models/test-model/1.0.0/model.zip",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 200
        mock_upload.assert_called_once()
    
    def test_upload_model_file_invalid_extension(self, client):
        """Test uploading non-ZIP file via model endpoint"""
        response = client.post(
            "/api/packages/models/test-model/1.0.0/model.zip",
            files={"file": ("test.txt", b"not a zip", "text/plain")}
        )
        assert response.status_code == 400
    
    @patch('src.routes.packages.upload_model')
    def test_upload_model_file_s3_error(self, mock_upload, client, mock_zip_file):
        """Test upload with S3 error"""
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "NoSuchBucket"}}
        mock_upload.side_effect = ClientError(error_response, "PutObject")
        
        response = client.post(
            "/api/packages/models/test-model/1.0.0/model.zip",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 500
    
    @patch('src.routes.packages.download_model')
    def test_download_model_file_with_component(self, mock_download, client):
        """Test downloading model with specific component"""
        mock_download.return_value = b"fake zip content"
        
        response = client.get(
            "/api/packages/models/test-model/1.0.0/model.zip",
            params={"component": "weights"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        mock_download.assert_called_once_with("test-model", "1.0.0", "weights", use_performance_path=False)
    
    @patch('src.routes.packages.reset_registry')
    def test_reset_system_via_packages(self, mock_reset, client):
        """Test resetting system via packages reset endpoint"""
        mock_reset.return_value = {"status": "ok"}
        
        response = client.post("/api/packages/reset")
        assert response.status_code == 200
        mock_reset.assert_called_once()
    
    @patch('src.routes.packages.sync_model_lineage_to_neptune')
    def test_sync_neptune(self, mock_sync, client):
        """Test syncing to Neptune"""
        mock_sync.return_value = {"status": "success"}
        
        response = client.post("/api/packages/sync-neptune")
        assert response.status_code == 200
        mock_sync.assert_called_once()
    
    @patch('src.routes.packages.get_model_lineage_from_config')
    def test_get_model_lineage_from_config_api(self, mock_lineage, client):
        """Test getting model lineage from config"""
        mock_lineage.return_value = {
            "lineage_metadata": {},
            "lineage_map": {}
        }
        
        response = client.get("/api/packages/models/test-model/1.0.0/lineage")
        assert response.status_code == 200
        mock_lineage.assert_called_once_with("test-model", "1.0.0")
    
    @patch('src.routes.packages.get_model_sizes')
    def test_get_model_sizes_api(self, mock_sizes, client):
        """Test getting model sizes"""
        mock_sizes.return_value = {
            "full": 1000000,
            "weights": 500000
        }
        
        response = client.get("/api/packages/models/test-model/1.0.0/size")
        assert response.status_code == 200
        data = response.json()
        assert "full" in data
        mock_sizes.assert_called_once_with("test-model", "1.0.0")
    
    @patch('src.routes.packages.model_ingestion')
    def test_ingest_model(self, mock_ingest, client):
        """Test ingesting a model"""
        mock_ingest.return_value = {
            "status": "success",
            "model_id": "test-model"
        }
        
        response = client.post(
            "/api/packages/models/ingest",
            params={"model_id": "test-model", "version": "main"}
        )
        assert response.status_code == 200
        mock_ingest.assert_called_once_with("test-model", "main")
    
    @patch('src.routes.packages.model_ingestion')
    def test_ingest_model_default_version(self, mock_ingest, client):
        """Test ingesting model with default version"""
        mock_ingest.return_value = {"status": "success"}
        
        response = client.post(
            "/api/packages/models/ingest",
            params={"model_id": "test-model"}
        )
        assert response.status_code == 200
        mock_ingest.assert_called_once_with("test-model", "main")
    
    @patch('src.routes.packages.list_models')
    def test_list_packages_with_continuation_token(self, mock_list_models, client):
        """Test listing packages with continuation token"""
        mock_list_models.return_value = {
            "models": [{"name": "test-model", "version": "1.0.0"}],
            "next_token": "token123"
        }
        
        response = client.get(
            "/api/packages",
            params={"continuation_token": "token123", "limit": 50}
        )
        assert response.status_code == 200
        data = response.json()
        assert "packages" in data
        assert "next_token" in data
        mock_list_models.assert_called_once()
    
    @patch('src.routes.packages.list_models')
    def test_list_packages_with_version_range(self, mock_list_models, client):
        """Test listing packages with version range"""
        mock_list_models.return_value = {"models": [], "next_token": None}
        
        response = client.get(
            "/api/packages",
            params={"version_range": "1.0.0-2.0.0"}
        )
        assert response.status_code == 200
        mock_list_models.assert_called_once()
    
    @patch('src.routes.packages.upload_model')
    def test_upload_package_with_debloat(self, mock_upload, client, mock_zip_file):
        """Test uploading package with debloat option"""
        mock_upload.return_value = {"status": "success"}
        
        response = client.post(
            "/api/packages/upload",
            files={"file": ("test.zip", mock_zip_file, "application/zip")},
            params={"debloat": True}
        )
        assert response.status_code == 200
        # Verify debloat parameter is passed
        call_args = mock_upload.call_args
        assert len(call_args[0]) >= 4  # file_content, model_id, version, debloat
        if len(call_args[0]) > 3:
            assert call_args[0][3] is True
    
    # Error path tests to improve coverage
    @patch('src.services.rating.run_scorer')
    def test_rate_package_http_exception(self, mock_scorer, client):
        """Test rate_package with HTTPException"""
        from fastapi import HTTPException
        mock_scorer.side_effect = HTTPException(status_code=404, detail="Not found")
        
        response = client.get("/api/packages/rate/test-model")
        assert response.status_code == 404
    
    @patch('src.services.rating.run_scorer')
    def test_rate_package_generic_exception(self, mock_scorer, client):
        """Test rate_package with generic exception"""
        mock_scorer.side_effect = Exception("Unexpected error")
        
        response = client.get("/api/packages/rate/test-model")
        assert response.status_code == 500
    
    @patch('src.routes.packages.list_models')
    def test_search_packages_http_exception(self, mock_list, client):
        """Test search_packages with HTTPException"""
        from fastapi import HTTPException
        mock_list.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.get("/api/packages/search", params={"q": "test"})
        assert response.status_code == 400
    
    @patch('src.routes.packages.list_models')
    def test_search_packages_generic_exception(self, mock_list, client):
        """Test search_packages with generic exception"""
        mock_list.side_effect = Exception("Unexpected error")
        
        response = client.get("/api/packages/search", params={"q": "test"})
        assert response.status_code == 500
    
    @patch('src.routes.packages.list_models')
    def test_search_model_cards_http_exception(self, mock_list, client):
        """Test search_model_cards with HTTPException"""
        from fastapi import HTTPException
        mock_list.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.get("/api/packages/search/model-cards", params={"q": "test"})
        assert response.status_code == 400
    
    @patch('src.routes.packages.list_models')
    def test_search_model_cards_generic_exception(self, mock_list, client):
        """Test search_model_cards with generic exception"""
        mock_list.side_effect = Exception("Unexpected error")
        
        response = client.get("/api/packages/search/model-cards", params={"q": "test"})
        assert response.status_code == 500
    
    @patch('src.routes.packages.list_models')
    def test_advanced_search_http_exception(self, mock_list, client):
        """Test advanced_search with HTTPException"""
        from fastapi import HTTPException
        mock_list.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.get(
            "/api/packages/search/advanced", params={"name_regex": "test.*"}
        )
        assert response.status_code == 400
    
    @patch('src.routes.packages.list_models')
    def test_advanced_search_generic_exception(self, mock_list, client):
        """Test advanced_search with generic exception"""
        mock_list.side_effect = Exception("Unexpected error")
        
        response = client.get(
            "/api/packages/search/advanced", params={"name_regex": "test.*"}
        )
        assert response.status_code == 500
    
    @patch('src.routes.packages.list_models')
    def test_list_packages_http_exception(self, mock_list, client):
        """Test list_packages with HTTPException"""
        from fastapi import HTTPException
        mock_list.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.get("/api/packages")
        assert response.status_code == 400
    
    @patch('src.routes.packages.list_models')
    def test_list_packages_generic_exception(self, mock_list, client):
        """Test list_packages with generic exception"""
        mock_list.side_effect = Exception("Unexpected error")
        
        response = client.get("/api/packages")
        assert response.status_code == 500
    
    @patch('src.routes.packages.upload_model')
    def test_upload_model_file_http_exception(self, mock_upload, client, mock_zip_file):
        """Test upload_model_file with HTTPException"""
        from fastapi import HTTPException
        mock_upload.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.post(
            "/api/packages/models/test-model/1.0.0/model.zip",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 400
    
    @patch('src.routes.packages.upload_model')
    def test_upload_model_file_access_denied(self, mock_upload, client, mock_zip_file):
        """Test upload_model_file with AccessDenied error"""
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "AccessDenied"}}
        mock_upload.side_effect = ClientError(error_response, "PutObject")
        
        response = client.post(
            "/api/packages/models/test-model/1.0.0/model.zip",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 500
        assert "Access denied" in response.json()["detail"]
    
    @patch('src.routes.packages.upload_model')
    def test_upload_model_file_other_s3_error(self, mock_upload, client, mock_zip_file):
        """Test upload_model_file with other S3 error"""
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "InvalidRequest"}}
        mock_upload.side_effect = ClientError(error_response, "PutObject")
        
        response = client.post(
            "/api/packages/models/test-model/1.0.0/model.zip",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 500
        assert "InvalidRequest" in response.json()["detail"]
    
    @patch('src.routes.packages.upload_model')
    def test_upload_model_file_generic_exception(
        self, mock_upload, client, mock_zip_file
    ):
        """Test upload_model_file with generic exception"""
        mock_upload.side_effect = Exception("Unexpected error")
        
        response = client.post(
            "/api/packages/models/test-model/1.0.0/model.zip",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 500
    
    @patch('src.routes.packages.download_model')
    def test_download_model_file_http_exception(self, mock_download, client):
        """Test download_model_file with HTTPException"""
        from fastapi import HTTPException
        mock_download.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.get("/api/packages/models/test-model/1.0.0/model.zip")
        assert response.status_code == 400
    
    @patch('src.routes.packages.download_model')
    def test_download_model_file_no_such_bucket(self, mock_download, client):
        """Test download_model_file with NoSuchBucket error"""
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "NoSuchBucket"}}
        mock_download.side_effect = ClientError(error_response, "GetObject")
        
        response = client.get("/api/packages/models/test-model/1.0.0/model.zip")
        assert response.status_code == 500
        assert "S3 bucket not found" in response.json()["detail"]
    
    @patch('src.routes.packages.download_model')
    def test_download_model_file_access_denied(self, mock_download, client):
        """Test download_model_file with AccessDenied error"""
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "AccessDenied"}}
        mock_download.side_effect = ClientError(error_response, "GetObject")
        
        response = client.get("/api/packages/models/test-model/1.0.0/model.zip")
        assert response.status_code == 500
        assert "Access denied" in response.json()["detail"]
    
    @patch('src.routes.packages.download_model')
    def test_download_model_file_other_s3_error(self, mock_download, client):
        """Test download_model_file with other S3 error"""
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "InvalidRequest"}}
        mock_download.side_effect = ClientError(error_response, "GetObject")
        
        response = client.get("/api/packages/models/test-model/1.0.0/model.zip")
        assert response.status_code == 500
        assert "InvalidRequest" in response.json()["detail"]
    
    @patch('src.routes.packages.download_model')
    def test_download_model_file_generic_exception(self, mock_download, client):
        """Test download_model_file with generic exception"""
        mock_download.side_effect = Exception("Unexpected error")
        
        response = client.get("/api/packages/models/test-model/1.0.0/model.zip")
        assert response.status_code == 500
    
    @patch('src.routes.packages.upload_model')
    def test_upload_package_http_exception(self, mock_upload, client, mock_zip_file):
        """Test upload_package with HTTPException"""
        from fastapi import HTTPException
        mock_upload.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.post(
            "/api/packages/upload",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 400
    
    @patch('src.routes.packages.upload_model')
    def test_upload_package_generic_exception(self, mock_upload, client, mock_zip_file):
        """Test upload_package with generic exception"""
        mock_upload.side_effect = Exception("Unexpected error")
        
        response = client.post(
            "/api/packages/upload",
            files={"file": ("test.zip", mock_zip_file, "application/zip")}
        )
        assert response.status_code == 500
    
    @patch('src.routes.packages.reset_registry')
    def test_reset_system_http_exception(self, mock_reset, client):
        """Test reset_system with HTTPException"""
        from fastapi import HTTPException
        mock_reset.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.post("/api/packages/reset")
        assert response.status_code == 400
    
    @patch('src.routes.packages.reset_registry')
    def test_reset_system_generic_exception(self, mock_reset, client):
        """Test reset_system with generic exception"""
        mock_reset.side_effect = Exception("Unexpected error")
        
        response = client.post("/api/packages/reset")
        assert response.status_code == 500
    
    @patch('src.routes.packages.sync_model_lineage_to_neptune')
    def test_sync_neptune_http_exception(self, mock_sync, client):
        """Test sync_neptune with HTTPException"""
        from fastapi import HTTPException
        mock_sync.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.post("/api/packages/sync-neptune")
        assert response.status_code == 400
    
    @patch('src.routes.packages.sync_model_lineage_to_neptune')
    def test_sync_neptune_generic_exception(self, mock_sync, client):
        """Test sync_neptune with generic exception"""
        mock_sync.side_effect = Exception("Unexpected error")
        
        response = client.post("/api/packages/sync-neptune")
        assert response.status_code == 500
    
    @patch('src.routes.packages.get_model_lineage_from_config')
    def test_get_model_lineage_http_exception(self, mock_lineage, client):
        """Test get_model_lineage_from_config_api with HTTPException"""
        from fastapi import HTTPException
        mock_lineage.side_effect = HTTPException(status_code=404, detail="Not found")
        
        response = client.get("/api/packages/models/test-model/1.0.0/lineage")
        assert response.status_code == 404
    
    @patch('src.routes.packages.get_model_lineage_from_config')
    def test_get_model_lineage_generic_exception(self, mock_lineage, client):
        """Test get_model_lineage_from_config_api with generic exception"""
        mock_lineage.side_effect = Exception("Unexpected error")
        
        response = client.get("/api/packages/models/test-model/1.0.0/lineage")
        assert response.status_code == 500
    
    @patch('src.routes.packages.get_model_sizes')
    def test_get_model_sizes_http_exception(self, mock_sizes, client):
        """Test get_model_sizes_api with HTTPException"""
        from fastapi import HTTPException
        mock_sizes.side_effect = HTTPException(status_code=404, detail="Not found")
        
        response = client.get("/api/packages/models/test-model/1.0.0/size")
        assert response.status_code == 404
    
    @patch('src.routes.packages.get_model_sizes')
    def test_get_model_sizes_generic_exception(self, mock_sizes, client):
        """Test get_model_sizes_api with generic exception"""
        mock_sizes.side_effect = Exception("Unexpected error")
        
        response = client.get("/api/packages/models/test-model/1.0.0/size")
        assert response.status_code == 500
    
    @patch('src.routes.packages.model_ingestion')
    def test_ingest_model_http_exception(self, mock_ingest, client):
        """Test ingest_model with HTTPException"""
        from fastapi import HTTPException
        mock_ingest.side_effect = HTTPException(status_code=400, detail="Bad request")
        
        response = client.post(
            "/api/packages/models/ingest",
            params={"model_id": "test-model"}
        )
        assert response.status_code == 400
    
    @patch('src.routes.packages.model_ingestion')
    def test_ingest_model_generic_exception(self, mock_ingest, client):
        """Test ingest_model with generic exception"""
        mock_ingest.side_effect = Exception("Unexpected error")
        
        response = client.post(
            "/api/packages/models/ingest",
            params={"model_id": "test-model"}
        )
        assert response.status_code == 500