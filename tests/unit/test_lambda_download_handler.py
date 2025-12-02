"""
Unit tests for Lambda download handler
"""
import json
import base64
import os
import importlib.util
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock
import pytest
from botocore.exceptions import ClientError

# Import lambda module using importlib to avoid keyword conflict
lambda_module_path = Path(__file__).parent.parent.parent / "src" / "lambda" / "download_handler.py"
spec = importlib.util.spec_from_file_location("download_handler", lambda_module_path)
download_handler_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download_handler_module)
lambda_handler = download_handler_module.lambda_handler


class TestLambdaDownloadHandler:
    """Test lambda_handler function"""

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_success(self, mock_sts, mock_s3):
        """Test successful download handler execution"""
        # Mock STS
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        # Mock S3 response
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = MagicMock()
        mock_response["Body"].read.return_value = b"test file content"
        
        mock_s3.get_object.return_value = mock_response
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {
                "component": "full"
            }
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        assert result["headers"]["Content-Type"] == "application/zip"
        assert "isBase64Encoded" in result
        assert result["isBase64Encoded"] is True
        assert base64.b64decode(result["body"]) == b"test file content"

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_missing_model_id(self, mock_sts, mock_s3):
        """Test handler with missing model_id parameter"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        event = {
            "pathParameters": {},
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert "detail" in body
        assert "model_id" in body["detail"].lower()

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_none_path_parameters(self, mock_sts, mock_s3):
        """Test handler with None pathParameters"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        event = {
            "pathParameters": None,
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 400

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_s3_no_such_key(self, mock_sts, mock_s3):
        """Test handler with S3 NoSuchKey error"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        error_response = {
            "Error": {
                "Code": "NoSuchKey"
            }
        }
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert "detail" in body
        assert "not found" in body["detail"].lower()

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_s3_no_such_bucket(self, mock_sts, mock_s3):
        """Test handler with S3 NoSuchBucket error"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        error_response = {
            "Error": {
                "Code": "NoSuchBucket"
            }
        }
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "detail" in body
        assert "bucket" in body["detail"].lower()

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_s3_access_denied(self, mock_sts, mock_s3):
        """Test handler with S3 AccessDenied error"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        error_response = {
            "Error": {
                "Code": "AccessDenied"
            }
        }
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "detail" in body
        assert "access denied" in body["detail"].lower() or "denied" in body["detail"].lower()

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_s3_other_error(self, mock_sts, mock_s3):
        """Test handler with other S3 error"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        error_response = {
            "Error": {
                "Code": "InternalError"
            }
        }
        mock_s3.get_object.side_effect = ClientError(error_response, "GetObject")
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        with pytest.raises(ClientError):
            lambda_handler(event, context)

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_default_version(self, mock_sts, mock_s3):
        """Test handler with default version"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = MagicMock()
        mock_response["Body"].read.return_value = b"test content"
        mock_s3.get_object.return_value = mock_response
        
        event = {
            "pathParameters": {
                "model_id": "test_model"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        # Verify S3 key uses default version "main"
        call_args = mock_s3.get_object.call_args
        assert "main" in str(call_args)

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_custom_component(self, mock_sts, mock_s3):
        """Test handler with custom component parameter"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = MagicMock()
        mock_response["Body"].read.return_value = b"test content"
        mock_s3.get_object.return_value = mock_response
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "v1.0"
            },
            "queryStringParameters": {
                "component": "weights"
            }
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        assert "weights" in result["headers"]["Content-Disposition"]

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_custom_path_prefix(self, mock_sts, mock_s3):
        """Test handler with custom path_prefix"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = MagicMock()
        mock_response["Body"].read.return_value = b"test content"
        mock_s3.get_object.return_value = mock_response
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {
                "path_prefix": "custom"
            }
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        # Verify S3 key uses custom path prefix
        call_args = mock_s3.get_object.call_args
        assert "custom" in str(call_args)

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_exception_handling(self, mock_sts, mock_s3):
        """Test handler exception handling"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_s3.get_object.side_effect = Exception("Unexpected error")
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "detail" in body
        assert "error" in body["detail"].lower()

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_base64_encoding(self, mock_sts, mock_s3):
        """Test that file content is base64 encoded"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        file_content = b"binary file content \x00\x01\x02"
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = MagicMock()
        mock_response["Body"].read.return_value = file_content
        mock_s3.get_object.return_value = mock_response
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        assert result["isBase64Encoded"] is True
        decoded = base64.b64decode(result["body"])
        assert decoded == file_content

    @patch.object(download_handler_module, "s3")
    @patch.object(download_handler_module, "sts")
    def test_lambda_handler_content_length(self, mock_sts, mock_s3):
        """Test that Content-Length header is set correctly"""
        mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
        
        file_content = b"test content"
        mock_response = MagicMock()
        mock_response.__getitem__.return_value = MagicMock()
        mock_response["Body"].read.return_value = file_content
        mock_s3.get_object.return_value = mock_response
        
        event = {
            "pathParameters": {
                "model_id": "test_model",
                "version": "main"
            },
            "queryStringParameters": {}
        }
        context = MagicMock()
        
        result = lambda_handler(event, context)
        
        assert result["statusCode"] == 200
        assert result["headers"]["Content-Length"] == str(len(file_content))

