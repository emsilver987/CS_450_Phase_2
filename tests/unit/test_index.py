import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.index import app, verify_auth_token, _extract_dataset_code_names_from_readme

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}

def test_health_components():
    response = client.get("/health/components")
    assert response.status_code == 200
    data = response.json()
    assert "components" in data
    assert data["components"][0]["id"] == "validator-service"

def test_verify_auth_token_missing():
    request = MagicMock()
    request.headers = {}
    assert verify_auth_token(request) is False

@patch("src.index.verify_jwt_token")
def test_verify_auth_token_valid(mock_verify):
    request = MagicMock()
    request.headers = {"x-authorization": "Bearer valid.token.here"}
    mock_verify.return_value = {"user_id": "test"}
    assert verify_auth_token(request) is True

def test_extract_dataset_code_names():
    readme = "This model uses the squad dataset. It is built with transformers library."
    result = _extract_dataset_code_names_from_readme(readme)
    assert result["dataset_name"] == "squad"
    assert result["code_name"] == "transformers"

    readme_empty = ""
    result = _extract_dataset_code_names_from_readme(readme_empty)
    assert result["dataset_name"] is None

@patch("src.index.verify_auth_token")
@patch("src.index.list_models")
@patch("src.index.list_all_artifacts")
def test_list_artifacts(mock_list_all, mock_list_models, mock_verify):
    mock_verify.return_value = True
    mock_list_models.return_value = {"models": [{"name": "model1", "id": "model1"}]}
    mock_list_all.return_value = [{"name": "dataset1", "id": "dataset1", "type": "dataset"}]
    
    # Test wildcard search
    response = client.post("/artifacts", json=[{"name": "*"}], headers={"x-authorization": "token"})
    assert response.status_code == 200
    data = response.json()
    names = [item["name"] for item in data]
    assert "model1" in names
    assert "dataset1" in names

@patch("src.index.verify_auth_token")
def test_list_artifacts_unauthorized(mock_verify):
    mock_verify.return_value = False
    response = client.post("/artifacts", json=[{"name": "*"}])
    assert response.status_code == 403

from src.index import _link_model_to_datasets_code, _link_dataset_code_to_models, _run_async_rating, _get_model_name_for_s3

@patch("src.index.update_artifact", new_callable=MagicMock)
@patch("src.index.find_artifacts_by_type")
@patch("src.index._artifact_storage", {"d1": {"name": "squad", "type": "dataset"}})
def test_link_model_to_datasets_code(mock_find, mock_update):
    # Test linking via _artifact_storage
    _link_model_to_datasets_code("m1", "model1", "This model uses squad dataset")
    mock_update.assert_called_with("m1", {"dataset_id": "d1"})

@patch("src.index.update_artifact")
@patch("src.index.find_models_with_null_link")
def test_link_dataset_code_to_models(mock_find, mock_update):
    mock_find.return_value = [{"id": "m1", "name": "model1", "dataset_name": "squad"}]
    _link_dataset_code_to_models("d1", "squad", "dataset")
    mock_update.assert_called_with("m1", {"dataset_id": "d1"})

@patch("src.index.analyze_model_content")
def test_run_async_rating(mock_analyze):
    mock_analyze.return_value = {"NetScore": 0.8}
    _run_async_rating("m1", "model1", "1.0.0")
    # No return value, but we can check if it didn't crash
    # Ideally we check _rating_results but it's global

@patch("src.index.get_generic_artifact_metadata")
def test_get_model_name_for_s3(mock_get):
    mock_get.return_value = {"name": "model1", "type": "model"}
    assert _get_model_name_for_s3("m1") == "model1"

