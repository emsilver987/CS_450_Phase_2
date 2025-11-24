import io
import zipfile
import pytest
from src.services.package_service import validate_package_structure

def create_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buffer.getvalue()

def test_validate_package_structure_valid():
    content = create_zip({
        "package.json": "{}",
        "README.md": "# Test",
        "src/index.js": "console.log('hello')"
    })
    result = validate_package_structure(content)
    assert result["valid"] is True
    assert result["has_package_json"] is True
    assert result["has_readme"] is True
    assert result["has_src"] is True

def test_validate_package_structure_invalid_zip():
    result = validate_package_structure(b"not a zip")
    assert result["valid"] is False
    assert "Invalid ZIP file" in result["error"]

def test_validate_package_structure_missing_files():
    content = create_zip({
        "other.txt": "content"
    })
    result = validate_package_structure(content)
    assert result["valid"] is True
    assert result["has_package_json"] is False
    assert result["has_readme"] is False
    assert result["has_src"] is False

from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from src.services.package_service import app, verify_token

client = TestClient(app)

# Mock auth
def mock_verify_token():
    return {"user_id": "test_user", "groups": ["Group_106"]}

app.dependency_overrides[verify_token] = mock_verify_token

@patch("src.services.package_service.dynamodb")
def test_init_upload(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    response = client.post("/init", json={
        "pkg_name": "test-pkg",
        "version": "1.0.0",
        "description": "Test package"
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "upload_id" in data
    assert "expires_at" in data
    mock_table.put_item.assert_called_once()

@patch("src.services.package_service.dynamodb")
def test_list_packages(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.scan.return_value = {
        "Items": [
            {
                "pkg_key": "test/1.0.0",
                "pkg_name": "test",
                "version": "1.0.0",
                "created_at": "2023-01-01T00:00:00Z",
                "updated_at": "2023-01-01T00:00:00Z"
            }
        ]
    }
    
    response = client.get("/packages")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["pkg_name"] == "test"

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

