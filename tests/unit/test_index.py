import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys
import logging

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Mock boto3 and watchtower to prevent startup hangs and logging errors
with patch("boto3.client"), patch("watchtower.CloudWatchLogHandler") as MockHandler:
    # Ensure the mock handler has a valid integer level to prevent TypeError in logging module
    MockHandler.return_value.level = logging.INFO
    from src.index import app

client = TestClient(app)

@pytest.fixture
def mock_auth():
    with patch("src.index.verify_auth_token") as mock:
        mock.return_value = True
        yield mock

@pytest.fixture
def mock_s3_service():
    with patch("src.index.list_models") as mock_list:
        with patch("src.index.list_artifacts_from_s3") as mock_list_s3:
            yield {"list_models": mock_list, "list_artifacts_from_s3": mock_list_s3}

@pytest.fixture
def mock_artifact_storage():
    with patch("src.index.list_all_artifacts") as mock_list:
        with patch("src.index._artifact_storage", {}) as mock_storage:
            yield {"list_all_artifacts": mock_list, "storage": mock_storage}

def test_health_components():
    response = client.get("/health/components")
    assert response.status_code == 200
    data = response.json()
    assert "components" in data
    assert data["components"][0]["id"] == "validator-service"

def test_health_components_invalid_window():
    response = client.get("/health/components?windowMinutes=1")
    assert response.status_code == 400

def test_list_artifacts_no_auth():
    # Don't use mock_auth here
    with patch("src.index.verify_auth_token", return_value=False):
        response = client.post("/artifacts", json=[{"name": "*"}])
        assert response.status_code == 403

def test_list_artifacts_wildcard(mock_auth, mock_s3_service, mock_artifact_storage):
    # Mock S3 models
    mock_s3_service["list_models"].return_value = {
        "models": [{"name": "model1", "id": "id1"}]
    }
    # Mock DB artifacts
    mock_artifact_storage["list_all_artifacts"].return_value = [
        {"name": "dataset1", "id": "id2", "type": "dataset"}
    ]
    
    response = client.post("/artifacts", json=[{"name": "*"}])
    assert response.status_code == 200
    data = response.json()
    names = [d["name"] for d in data]
    assert "model1" in names
    assert "dataset1" in names

def test_list_artifacts_exact_match(mock_auth, mock_s3_service, mock_artifact_storage):
    # Mock DB artifacts
    mock_artifact_storage["list_all_artifacts"].return_value = [
        {"name": "target-pkg", "id": "id1", "type": "model"},
        {"name": "other-pkg", "id": "id2", "type": "dataset"}
    ]
    
    response = client.post("/artifacts", json=[{"name": "target-pkg"}])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "target-pkg"

def test_list_artifacts_filter_type(mock_auth, mock_s3_service, mock_artifact_storage):
    mock_artifact_storage["list_all_artifacts"].return_value = [
        {"name": "pkg1", "id": "id1", "type": "model"},
        {"name": "pkg2", "id": "id2", "type": "dataset"}
    ]
    
    # Filter for dataset
    response = client.post("/artifacts", json=[{"name": "*", "types": ["dataset"]}])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["type"] == "dataset"

def test_list_artifacts_invalid_body(mock_auth):
    response = client.post("/artifacts", json={"not": "a list"})
    assert response.status_code == 400

def test_list_artifacts_missing_name(mock_auth):
    response = client.post("/artifacts", json=[{"no_name": "here"}])
    assert response.status_code == 400
