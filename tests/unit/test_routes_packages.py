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
