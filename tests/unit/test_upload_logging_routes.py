import pytest
from unittest.mock import MagicMock, patch
from fastapi import Request, UploadFile
import io

# Import the functions to test
from src.routes.packages import upload_model_file, upload_package, ingest_model
from src.routes.frontend import upload_post, ingest_post

@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.headers = {"authorization": "Bearer test-token"}
    return request

@pytest.fixture
def mock_file():
    file = MagicMock(spec=UploadFile)
    file.filename = "test-model.zip"
    file.file = io.BytesIO(b"test content")
    return file

@patch("src.routes.packages.verify_jwt_token")
@patch("src.routes.packages.log_upload_event")
@patch("src.routes.packages.upload_model")
@patch("src.routes.packages.dynamodb")
def test_upload_model_file_logging(mock_dynamodb, mock_upload_model, mock_log, mock_verify, mock_request, mock_file):
    # Setup
    mock_verify.return_value = {"user_id": "test-user-1"}
    mock_upload_model.return_value = {"sha256": "hash123"}
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    # Execute
    upload_model_file(model_id="test-model", version="1.0.0", request=mock_request, file=mock_file)

    # Verify
    mock_log.assert_called_once()
    call_args = mock_log.call_args[1]
    assert call_args["artifact_name"] == "test-model"
    assert call_args["user_id"] == "test-user-1"
    assert call_args["status"] == "success"

@patch("src.routes.packages.verify_jwt_token")
@patch("src.routes.packages.log_upload_event")
@patch("src.routes.packages.upload_model")
@patch("src.routes.packages.dynamodb")
def test_upload_package_logging(mock_dynamodb, mock_upload_model, mock_log, mock_verify, mock_request, mock_file):
    # Setup
    mock_verify.return_value = {"user_id": "test-user-2"}
    mock_upload_model.return_value = {"sha256": "hash456"}
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    # Execute
    upload_package(request=mock_request, file=mock_file)

    # Verify
    mock_log.assert_called_once()
    call_args = mock_log.call_args[1]
    # In upload_package, model_id is derived from filename "test-model"
    assert call_args["artifact_name"] == "test-model" 
    assert call_args["user_id"] == "test-user-2"
    assert call_args["status"] == "success"

@patch("src.routes.packages.verify_jwt_token")
@patch("src.routes.packages.log_upload_event")
@patch("src.routes.packages.model_ingestion")
def test_ingest_model_logging(mock_ingest, mock_log, mock_verify, mock_request):
    # Setup
    mock_verify.return_value = {"user_id": "test-user-3"}
    mock_ingest.return_value = {"status": "ingested"}

    # Execute
    ingest_model(request=mock_request, model_id="test-ingest", version="main")

    # Verify
    mock_log.assert_called_once()
    call_args = mock_log.call_args[1]
    assert call_args["artifact_name"] == "test-ingest"
    assert call_args["user_id"] == "test-user-3"
    assert call_args["status"] == "success"

@patch("src.routes.frontend.verify_jwt_token")
@patch("src.routes.frontend.log_upload_event")
@patch("src.routes.frontend.upload_model")
@patch("src.routes.frontend.dynamodb")
def test_frontend_upload_post_logging(mock_dynamodb, mock_upload_model, mock_log, mock_verify, mock_request, mock_file):
    # Setup
    mock_verify.return_value = {"user_id": "test-user-4"}
    mock_upload_model.return_value = {"sha256": "hash789"}
    mock_table = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    # Execute
    upload_post(request=mock_request, file=mock_file, model_id="frontend-model", version="1.0.0")

    # Verify
    mock_log.assert_called_once()
    call_args = mock_log.call_args[1]
    assert call_args["artifact_name"] == "frontend-model"
    assert call_args["user_id"] == "test-user-4"
    assert call_args["status"] == "success"

@pytest.mark.asyncio
@patch("src.routes.frontend.verify_jwt_token")
@patch("src.routes.frontend.log_upload_event")
@patch("src.routes.frontend.model_ingestion")
async def test_frontend_ingest_post_logging(mock_ingest, mock_log, mock_verify, mock_request):
    # Setup
    mock_verify.return_value = {"user_id": "test-user-5"}
    mock_ingest.return_value = {"status": "ingested"}
    
    # Mock form data
    async def mock_form():
        return {"name": "frontend-ingest", "version": "main"}
    mock_request.form = mock_form

    # Execute
    await ingest_post(request=mock_request)

    # Verify
    mock_log.assert_called_once()
    call_args = mock_log.call_args[1]
    assert call_args["artifact_name"] == "frontend-ingest"
    assert call_args["user_id"] == "test-user-5"
    assert call_args["status"] == "success"
