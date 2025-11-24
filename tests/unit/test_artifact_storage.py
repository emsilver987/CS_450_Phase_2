import pytest
from unittest.mock import MagicMock, patch
from src.services.artifact_storage import (
    save_artifact, get_artifact, update_artifact, delete_artifact,
    list_all_artifacts, find_artifacts_by_type, find_artifacts_by_name,
    find_models_with_null_link, clear_all_artifacts,
    store_generic_artifact_metadata, get_generic_artifact_metadata
)

@patch("src.services.artifact_storage.dynamodb")
def test_save_artifact(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    result = save_artifact("id1", {
        "name": "model1",
        "type": "model",
        "version": "1.0.0",
        "url": "s3://bucket/model1"
    })
    
    assert result is True
    mock_table.put_item.assert_called_once()

@patch("src.services.artifact_storage.dynamodb")
def test_get_artifact(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {
            "artifact_id": "id1",
            "name": "model1",
            "type": "model",
            "version": "1.0.0",
            "url": "s3://bucket/model1"
        }
    }
    
    result = get_artifact("id1")
    assert result is not None
    assert result["id"] == "id1"
    assert result["name"] == "model1"

@patch("src.services.artifact_storage.dynamodb")
def test_update_artifact(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    result = update_artifact("id1", {"dataset_id": "d1"})
    assert result is True
    mock_table.update_item.assert_called_once()

@patch("src.services.artifact_storage.dynamodb")
def test_delete_artifact(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    result = delete_artifact("id1")
    assert result is True
    mock_table.delete_item.assert_called_once()

@patch("src.services.artifact_storage.dynamodb")
def test_list_all_artifacts(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.scan.return_value = {
        "Items": [
            {"artifact_id": "id1", "name": "model1", "type": "model"},
            {"artifact_id": "id2", "name": "dataset1", "type": "dataset"}
        ]
    }
    
    result = list_all_artifacts()
    assert len(result) == 2
    assert result[0]["id"] == "id1"
    assert result[1]["id"] == "id2"

@patch("src.services.artifact_storage.list_all_artifacts")
def test_find_artifacts_by_type(mock_list):
    mock_list.return_value = [
        {"id": "id1", "name": "model1", "type": "model"},
        {"id": "id2", "name": "dataset1", "type": "dataset"},
        {"id": "id3", "name": "model2", "type": "model"}
    ]
    
    result = find_artifacts_by_type("model")
    assert len(result) == 2
    assert all(a["type"] == "model" for a in result)

@patch("src.services.artifact_storage.list_all_artifacts")
def test_find_artifacts_by_name(mock_list):
    mock_list.return_value = [
        {"id": "id1", "name": "model1", "type": "model"},
        {"id": "id2", "name": "dataset1", "type": "dataset"}
    ]
    
    result = find_artifacts_by_name("model1")
    assert len(result) == 1
    assert result[0]["name"] == "model1"

@patch("src.services.artifact_storage.list_all_artifacts")
def test_find_models_with_null_link(mock_list):
    mock_list.return_value = [
        {"id": "m1", "type": "model", "dataset_name": "squad"},
        {"id": "m2", "type": "model", "dataset_id": "d1", "dataset_name": "squad"},
        {"id": "m3", "type": "model", "code_name": "bert"}
    ]
    
    result = find_models_with_null_link("dataset")
    assert len(result) == 1
    assert result[0]["id"] == "m1"

@patch("src.services.artifact_storage.dynamodb")
def test_clear_all_artifacts(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    with patch("src.services.artifact_storage.list_all_artifacts") as mock_list:
        mock_list.return_value = [
            {"id": "id1", "name": "model1"},
            {"id": "id2", "name": "model2"}
        ]
        
        result = clear_all_artifacts()
        assert result is True
        assert mock_table.delete_item.call_count == 2

@patch("src.services.artifact_storage.dynamodb")
def test_store_generic_artifact_metadata(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    
    store_generic_artifact_metadata("model", "id1", {
        "name": "model1",
        "version": "1.0.0",
        "extra_data": {"key": "value"}
    })
    
    mock_table.put_item.assert_called_once()

@patch("src.services.artifact_storage.dynamodb")
def test_get_generic_artifact_metadata(mock_dynamodb):
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    mock_table.get_item.return_value = {
        "Item": {
            "artifact_id": "id1",
            "type": "model",
            "name": "model1",
            "metadata_json": '{"name": "model1", "version": "1.0.0"}'
        }
    }
    
    result = get_generic_artifact_metadata("model", "id1")
    assert result is not None
    assert result["name"] == "model1"
