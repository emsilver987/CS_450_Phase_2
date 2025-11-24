import pytest
import io
import zipfile
import json
from unittest.mock import MagicMock, patch
from src.services.s3_service import (
    parse_version, version_matches_range, validate_huggingface_structure,
    upload_model, download_model, list_models, store_artifact_metadata,
    find_artifact_metadata_by_id
)

def test_parse_version():
    assert parse_version("1.2.3") == (1, 2, 3)
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("invalid") is None

def test_version_matches_range():
    assert version_matches_range("1.2.3", "1.2.3") is True
    assert version_matches_range("1.2.3", "^1.2.0") is True
    assert version_matches_range("1.2.3", "~1.2.0") is True
    assert version_matches_range("2.0.0", "^1.2.0") is False
    assert version_matches_range("1.3.0", "~1.2.0") is False
    assert version_matches_range("1.2.3", "1.2.0-1.3.0") is True

def create_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buffer.getvalue()

def test_validate_huggingface_structure():
    valid_zip = create_zip({
        "config.json": "{}",
        "model.bin": "data"
    })
    result = validate_huggingface_structure(valid_zip)
    assert result["valid"] is True

    invalid_zip = create_zip({
        "readme.md": "# test"
    })
    result = validate_huggingface_structure(invalid_zip)
    assert result["valid"] is False

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
def test_upload_model(mock_s3):
    content = b"zipcontent"
    result = upload_model(content, "test-model", "1.0.0")
    assert result["message"] == "Upload successful"
    mock_s3.put_object.assert_called_once()

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
def test_download_model(mock_s3):
    mock_response = MagicMock()
    mock_response.__getitem__.return_value.read.return_value = b"zipcontent"
    mock_s3.get_object.return_value = mock_response
    
    content = download_model("test-model", "1.0.0")
    assert content == b"zipcontent"
    mock_s3.get_object.assert_called_once()

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
def test_list_models(mock_s3):
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "models/model1/1.0.0/model.zip"},
            {"Key": "models/model2/2.0.0/model.zip"}
        ]
    }
    
    result = list_models()
    assert len(result["models"]) == 2
    assert result["models"][0]["name"] == "model1"

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
def test_store_artifact_metadata(mock_s3):
    result = store_artifact_metadata("id1", "name1", "dataset", "1.0.0", "s3://url")
    assert result["status"] == "success"
    mock_s3.put_object.assert_called_once()

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
@patch("src.services.s3_service.list_models")
def test_find_artifact_metadata_by_id(mock_list_models, mock_s3):
    # Mock list_models to return nothing to force comprehensive search
    mock_list_models.return_value = {"models": []}
    
    # Mock paginator for comprehensive search
    mock_paginator = MagicMock()
    mock_s3.get_paginator.return_value = mock_paginator
    
    # Mock page with metadata file
    mock_paginator.paginate.return_value = [
        {"Contents": [{"Key": "datasets/name1/1.0.0/metadata.json"}]}
    ]
    
    # Mock get_object for metadata
    mock_response = MagicMock()
    metadata = {
        "artifact_id": "id1",
        "name": "name1",
        "type": "dataset",
        "version": "1.0.0",
        "url": "s3://url"
    }
    mock_response.__getitem__.return_value.read.return_value = json.dumps(metadata).encode("utf-8")
    mock_s3.get_object.return_value = mock_response
    
    result = find_artifact_metadata_by_id("id1")
    assert result is not None
    assert result["artifact_id"] == "id1"
    assert result["name"] == "name1"
