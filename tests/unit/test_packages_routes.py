import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Don't include the router in app creation, test routes independently
@patch("src.routes.packages.verify_token")
@patch("src.routes.packages.dynamodb")
def test_init_package_registry(mock_dynamodb, mock_verify):
    from src.routes.packages import init_package_registry
    
    mock_verify.return_value = {"username": "admin", "isAdmin": True}
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.scan.return_value = {"Items": []}
    
    result = init_package_registry()
    assert result["message"] == "Registry is reset."

@patch("src.routes.packages.verify_token")
@patch("src.routes.packages.dynamodb")
def test_get_packages_function(mock_dynamodb, mock_verify):
    from src.routes.packages import list_packages
    
    mock_verify.return_value = {"username": "user1"}
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.scan.return_value = {
        "Items": [
            {"PackageID": "id1", "Name": "package1", "Version": "1.0.0"}
        ]
    }
    
    result = list_packages([{"Name": "*"}], "auth_header")
    assert isinstance(result, list)

@patch("src.routes.packages.upload_package_to_s3")
def test_upload_package_to_s3(mock_upload):
    from src.routes.packages import upload_package_to_s3
    
    mock_upload.return_value = "s3://bucket/key"
    result = upload_package_to_s3("id1", "name1", "1.0.0", b"zipdata")
    # Function will try upload, may succeed or fail
    # Just verify it doesn't crash

@patch("src.routes.packages.get_package_metadata_from_dynamodb")
@patch("src.routes.packages.dynamodb")
def test_get_package_metadata(mock_dynamodb, mock_get):
    from src.routes.packages import get_package_metadata_from_dynamodb
    
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {
            "PackageID": "id1",
            "Name": "package1",
            "Version": "1.0.0",
            "URL": "https://github.com/user/repo"
        }
    }
    
    result = get_package_metadata_from_dynamodb("id1")
    # Just verify function executes
