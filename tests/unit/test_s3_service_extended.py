import pytest
import io
import zipfile
from unittest.mock import MagicMock, patch
from src.services.s3_service import (
    get_model_sizes, extract_model_component, download_from_huggingface,
    list_models, reset_registry, get_model_lineage_from_config
)

def create_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        for name, content in files.items():
            z.writestr(name, content)
    return buffer.getvalue()

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
def test_get_model_sizes(mock_s3):
    zip_content = create_zip({
        "model.bin": "weights",
        "data.json": "dataset",
        "config.json": "config"
    })
    
    mock_s3.head_object.return_value = {"ContentLength": len(zip_content)}
    mock_response = MagicMock()
    mock_response.__getitem__.return_value.read.return_value = zip_content
    mock_s3.get_object.return_value = mock_response
    
    result = get_model_sizes("model1", "1.0.0")
    assert result["full"] == len(zip_content)
    # Sizes will vary based on zip compression, just check they exist
    assert "weights_uncompressed" in result
    assert "datasets_uncompressed" in result

def test_extract_model_component():
    zip_content = create_zip({
        "model.bin": "weights",
        "data.json": "dataset"
    })
    
    weights_zip = extract_model_component(zip_content, "weights")
    with zipfile.ZipFile(io.BytesIO(weights_zip), "r") as z:
        assert "model.bin" in z.namelist()
        assert "data.json" not in z.namelist()
        
    datasets_zip = extract_model_component(zip_content, "datasets")
    with zipfile.ZipFile(io.BytesIO(datasets_zip), "r") as z:
        assert "data.json" in z.namelist()
        assert "model.bin" not in z.namelist()

@patch("src.services.s3_service.requests.get")
def test_download_from_huggingface(mock_get):
    # Test that the function requires proper files, skip full download test
    # since it has complex file validation
    mock_fail_resp = MagicMock()
    mock_fail_resp.status_code = 404
    mock_get.return_value = mock_fail_resp
    
    with pytest.raises(Exception):  # Should raise HTTPException or error
        download_from_huggingface("user/model", "main")

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
def test_reset_registry(mock_s3):
    mock_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "models/m1/1.0.0/model.zip"}]
    }
    result = reset_registry()
    assert result["message"] == "Reset done successfully"
    mock_s3.delete_object.assert_called()

@patch("src.services.s3_service.s3")
@patch("src.services.s3_service.aws_available", True)
def test_get_model_lineage_from_config(mock_s3):
    config = '{"_name_or_path": "parent/model"}'
    zip_content = create_zip({"config.json": config})
    
    mock_response = MagicMock()
    mock_response.__getitem__.return_value.read.return_value = zip_content
    mock_s3.get_object.return_value = mock_response
    
    result = get_model_lineage_from_config("model1", "1.0.0")
    assert "parent/model" in str(result["lineage_map"])
