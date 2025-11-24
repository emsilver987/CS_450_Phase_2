import pytest
from unittest.mock import MagicMock, patch
from src.services.validator_service import (
    get_package_metadata, get_validator_script, log_download_event
)

@patch("src.services.validator_service.dynamodb")
def test_get_package_metadata(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {
            "PackageName": "test-package",
            "Version": "1.0.0",
            "Metadata": "{}"
        }
    }
    
    result = get_package_metadata("test-package", "1.0.0")
    assert result is not None

@patch("src.services.validator_service.s3")
def test_get_validator_script(mock_s3):
    mock_response = MagicMock()
    mock_response.__getitem__.return_value.read.return_value = b"// validator script"
    mock_s3.get_object.return_value = mock_response
    
    result = get_validator_script("test-package", "1.0.0")
    assert result is not None

@patch("src.services.validator_service.dynamodb")
def test_log_download_event(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    log_download_event("test-package", "1.0.0", "user1", "success")
    mock_table.put_item.assert_called_once()
