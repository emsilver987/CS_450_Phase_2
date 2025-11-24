import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from src.routes.frontend import setup_app, register_routes, set_templates

# Mock Jinja2Templates
mock_templates = MagicMock(spec=Jinja2Templates)
mock_templates.TemplateResponse.return_value = {"body": b"html content"}

# Setup app
app = FastAPI()
register_routes(app)
# Inject mock templates
set_templates(mock_templates)

client = TestClient(app)

@patch("src.routes.frontend.templates", mock_templates)
def test_home():
    response = client.get("/")
    assert response.status_code == 200
    mock_templates.TemplateResponse.assert_called()

@patch("src.routes.frontend.templates", mock_templates)
@patch("src.routes.frontend.list_models")
def test_directory(mock_list):
    mock_list.return_value = {"models": [{"name": "test", "version": "1.0.0"}]}
    response = client.get("/directory")
    assert response.status_code == 200
    mock_templates.TemplateResponse.assert_called()

@patch("src.routes.frontend.templates", mock_templates)
@patch("src.routes.frontend.run_scorer")
def test_rate_get(mock_scorer):
    mock_scorer.return_value = {"net_score": 0.8}
    response = client.get("/rate?name=test")
    assert response.status_code == 200
    mock_templates.TemplateResponse.assert_called()

@patch("src.routes.frontend.templates", mock_templates)
@patch("src.routes.frontend.run_scorer")
def test_rate_by_id(mock_scorer):
    mock_scorer.return_value = {"net_score": 0.8}
    response = client.get("/artifact/model/test-id/rate")
    assert response.status_code == 200
    mock_templates.TemplateResponse.assert_called()

@patch("src.routes.frontend.templates", mock_templates)
def test_upload_get():
    response = client.get("/upload")
    assert response.status_code == 200

@patch("src.routes.frontend.templates", mock_templates)
@patch("src.routes.frontend.upload_model")
def test_upload_post(mock_upload):
    mock_upload.return_value = {"message": "success"}
    files = {"file": ("test.zip", b"content", "application/zip")}
    response = client.post("/upload", files=files)
    assert response.status_code == 200
    assert response.json()["message"] == "Upload successful"

@patch("src.routes.frontend.templates", mock_templates)
def test_admin():
    response = client.get("/admin")
    assert response.status_code == 200

@patch("src.routes.frontend.templates", mock_templates)
@patch("src.services.s3_service.get_model_lineage_from_config")
def test_lineage(mock_lineage):
    mock_lineage.return_value = {"lineage_map": {}}
    response = client.get("/lineage?name=test")
    assert response.status_code == 200

@patch("src.routes.frontend.templates", mock_templates)
@patch("src.services.s3_service.get_model_sizes")
def test_size_cost(mock_sizes):
    mock_sizes.return_value = {"full": 100}
    response = client.get("/size-cost?name=test")
    assert response.status_code == 200

@patch("src.routes.frontend.templates", mock_templates)
def test_ingest_get():
    response = client.get("/ingest")
    assert response.status_code == 200

@patch("src.routes.frontend.templates", mock_templates)
@patch("src.services.s3_service.model_ingestion")
def test_ingest_post(mock_ingest):
    mock_ingest.return_value = {"status": "success"}
    response = client.post("/ingest", data={"name": "test", "version": "main"})
    assert response.status_code == 200

@patch("src.routes.frontend.download_model")
def test_download(mock_download):
    mock_download.return_value = b"zipcontent"
    response = client.get("/download/test/1.0.0")
    assert response.status_code == 200
    assert response.content == b"zipcontent"

@patch("src.routes.frontend.reset_registry")
def test_reset(mock_reset):
    mock_reset.return_value = {"message": "reset"}
    response = client.post("/admin/reset")
    assert response.status_code == 200
