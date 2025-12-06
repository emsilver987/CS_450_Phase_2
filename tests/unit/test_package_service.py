import pytest
from unittest.mock import patch, MagicMock
import os
import json
from datetime import datetime, timezone

# Import helper from conftest
try:
    from tests.conftest import get_test_client, HTTPX_AVAILABLE
except ImportError:
    # Fallback if conftest not available
    try:
        import httpx
        HTTPX_AVAILABLE = True
    except ImportError:
        HTTPX_AVAILABLE = False
    def get_test_client(app):
        if HTTPX_AVAILABLE:
            from fastapi.testclient import TestClient
            return TestClient(app)
        else:
            class MockTestClient:
                def __init__(self, app):
                    self.app = app
                def __getattr__(self, name):
                    def skip_method(*args, **kwargs):
                        pytest.skip("httpx not installed")
                    return skip_method
                def get(self, *args, **kwargs):
                    pytest.skip("httpx not installed")
                def post(self, *args, **kwargs):
                    pytest.skip("httpx not installed")
                def put(self, *args, **kwargs):
                    pytest.skip("httpx not installed")
                def delete(self, *args, **kwargs):
                    pytest.skip("httpx not installed")
            return MockTestClient(app)

# Mock environment variables
os.environ["AWS_REGION"] = "us-east-1"
os.environ["ARTIFACTS_BUCKET"] = "test-artifacts-bucket"
os.environ["DDB_TABLE_PACKAGES"] = "test-packages-table"
os.environ["DDB_TABLE_UPLOADS"] = "test-uploads-table"

from src.services.package_service import app

client = get_test_client(app)

@pytest.fixture
def mock_aws():
    with patch("src.services.package_service.s3") as mock_s3, \
         patch("src.services.package_service.dynamodb") as mock_ddb:
        
        # Setup DynamoDB Table mocks
        mock_table = MagicMock()
        mock_ddb.Table.return_value = mock_table
        
        yield {"s3": mock_s3, "dynamodb": mock_ddb, "table": mock_table}

@pytest.fixture
def mock_auth():
    # Override the dependency directly
    from src.services.package_service import verify_token
    app.dependency_overrides[verify_token] = lambda: {"user_id": "test-user", "groups": ["test-group"]}
    yield
    app.dependency_overrides = {}

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_init_upload(mock_aws, mock_auth):
    response = client.post(
        "/init",
        json={
            "pkg_name": "test-package",
            "version": "1.0.0",
            "description": "Test package",
            "is_sensitive": False
        },
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "upload_id" in data
    
    # Verify DynamoDB put_item called
    mock_aws["table"].put_item.assert_called_once()

def test_upload_part(mock_aws, mock_auth):
    # Mock get_item for upload metadata
    mock_aws["table"].get_item.return_value = {
        "Item": {
            "upload_id": "test-id",
            "pkg_name": "test-pkg",
            "version": "1.0.0",
            "user_id": "test-user",
            "expires_at": "2099-01-01T00:00:00Z"
        }
    }
    
    # Mock S3 put_object
    mock_aws["s3"].put_object.return_value = {"ETag": '"test-etag"'}
    
    files = {"file": ("part1", b"content", "application/octet-stream")}
    response = client.post(
        "/part/test-id?part_number=1",
        files=files,
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert response.json()["etag"] == "test-etag"

def test_commit_upload(mock_aws, mock_auth):
    # Mock get_item
    mock_aws["table"].get_item.return_value = {
        "Item": {
            "upload_id": "test-id",
            "pkg_name": "test-pkg",
            "version": "1.0.0",
            "user_id": "test-user",
            "is_sensitive": False,
            "allowed_groups": [],
            "description": "desc"
        }
    }
    
    # Mock S3 multipart
    mock_aws["s3"].create_multipart_upload.return_value = {"UploadId": "s3-upload-id"}
    mock_aws["s3"].upload_part_copy.return_value = {"CopyPartResult": {"ETag": "etag-1"}}
    
    response = client.post(
        "/commit/test-id",
        json={
            "upload_id": "test-id",
            "parts": [{"ETag": "etag-1", "PartNumber": "1"}]
        },
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Upload completed successfully"

def test_abort_upload(mock_aws, mock_auth):
    mock_aws["table"].get_item.return_value = {
        "Item": {
            "upload_id": "test-id",
            "user_id": "test-user"
        }
    }
    
    response = client.post("/abort/test-id", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    mock_aws["table"].update_item.assert_called_once()

def test_download_url(mock_aws, mock_auth):
    mock_aws["table"].get_item.return_value = {
        "Item": {
            "pkg_key": "pkg/1.0.0",
            "is_sensitive": False
        }
    }
    mock_aws["s3"].generate_presigned_url.return_value = "http://s3-url"
    
    response = client.get("/download/pkg/1.0.0", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["url"] == "http://s3-url"

def test_list_packages(mock_aws, mock_auth):
    mock_aws["table"].scan.return_value = {
        "Items": [
            {
                "pkg_key": "pkg/1.0.0",
                "pkg_name": "pkg",
                "version": "1.0.0",
                "created_at": "now",
                "updated_at": "now"
            }
        ]
    }
    
    response = client.get("/packages", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert len(response.json()) == 1

