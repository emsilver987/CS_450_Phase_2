"""
Unit tests for validator_service
"""
import pytest
from unittest.mock import patch, MagicMock
from unittest.mock import patch as patch_module
import src.services.validator_service as validator_service_module


class TestValidatorService:
    """Test validator service functions"""

    @patch_module.object(validator_service_module, 'dynamodb', autospec=True)
    def test_get_package_metadata_success(self, mock_dynamodb):
        """Test getting package metadata successfully"""
        from src.services.validator_service import get_package_metadata
        
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            "Item": {"pkg_key": "test-pkg/1.0.0", "name": "test-pkg"}
        }
        mock_dynamodb.Table.return_value = mock_table
        
        result = get_package_metadata("test-pkg", "1.0.0")
        assert result is not None
        assert result["name"] == "test-pkg"

    @patch_module.object(validator_service_module, 'dynamodb', autospec=True)
    def test_get_package_metadata_not_found(self, mock_dynamodb):
        """Test getting package metadata when not found"""
        from src.services.validator_service import get_package_metadata
        
        mock_table = MagicMock()
        mock_table.get_item.return_value = {}
        mock_dynamodb.Table.return_value = mock_table
        
        result = get_package_metadata("nonexistent", "1.0.0")
        assert result is None

    @patch_module.object(validator_service_module, 'dynamodb', autospec=True)
    def test_get_package_metadata_exception(self, mock_dynamodb):
        """Test getting package metadata with exception"""
        from src.services.validator_service import get_package_metadata
        
        mock_table = MagicMock()
        mock_table.get_item.side_effect = Exception("DB error")
        mock_dynamodb.Table.return_value = mock_table
        
        result = get_package_metadata("test-pkg", "1.0.0")
        assert result is None

    @patch_module.object(validator_service_module, 's3', autospec=True)
    def test_get_validator_script_success(self, mock_s3):
        """Test getting validator script successfully"""
        from src.services.validator_service import get_validator_script
        
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b"def validate(data): return True")
        }
        
        result = get_validator_script("test-pkg", "1.0.0")
        assert result is not None
        assert "validate" in result

    @patch_module.object(validator_service_module, 's3', autospec=True)
    def test_get_validator_script_not_found(self, mock_s3):
        """Test getting validator script when not found"""
        from src.services.validator_service import get_validator_script
        from botocore.exceptions import ClientError
        
        # Create a NoSuchKey exception class
        class NoSuchKey(ClientError):
            pass
        
        # Create a proper exceptions namespace
        mock_exceptions = MagicMock()
        mock_exceptions.NoSuchKey = NoSuchKey
        mock_s3.exceptions = mock_exceptions
        mock_s3.get_object.side_effect = NoSuchKey(
            {'Error': {'Code': 'NoSuchKey', 'Message': 'Not found'}},
            'GetObject'
        )
        
        result = get_validator_script("test-pkg", "1.0.0")
        assert result is None

    @patch_module.object(validator_service_module, 's3', autospec=True)
    def test_get_validator_script_exception(self, mock_s3):
        """Test getting validator script with exception"""
        from src.services.validator_service import get_validator_script
        from botocore.exceptions import ClientError
        
        # Create a proper exceptions namespace with a real exception class
        class NoSuchKeyError(ClientError):
            pass
        
        mock_exceptions = MagicMock()
        mock_exceptions.NoSuchKey = NoSuchKeyError
        mock_s3.exceptions = mock_exceptions
        
        # Use a different exception that will be caught by the second except clause
        mock_s3.get_object.side_effect = ValueError("S3 error")
        
        result = get_validator_script("test-pkg", "1.0.0")
        assert result is None

    def test_run_validator_script_success(self):
        """Test running validator script successfully"""
        from src.services.validator_service import _run_validator_script
        
        script = "def validate(data): return {'valid': True, 'score': 0.9}"
        data = {"name": "test-pkg"}
        
        result = _run_validator_script(script, data)
        assert result["valid"] is True
        assert "result" in result

    def test_run_validator_script_no_validate_function(self):
        """Test running validator script without validate function"""
        from src.services.validator_service import _run_validator_script
        
        script = "def other_function(): pass"
        data = {"name": "test-pkg"}
        
        with pytest.raises(ValueError, match="must define a validate"):
            _run_validator_script(script, data)

    def test_run_validator_script_returns_none(self):
        """Test running validator script that returns None"""
        from src.services.validator_service import _run_validator_script
        
        script = "def validate(data): return None"
        data = {"name": "test-pkg"}
        
        with pytest.raises(ValueError, match="returned no result"):
            _run_validator_script(script, data)

    @patch_module.object(validator_service_module, 'cloudwatch', autospec=True)
    @patch('src.services.validator_service.get_context')
    def test_execute_validator_success(self, mock_context, mock_cloudwatch):
        """Test executing validator successfully"""
        from src.services.validator_service import execute_validator
        from multiprocessing import Queue
        
        script = "def validate(data): return {'valid': True}"
        data = {"name": "test-pkg"}
        
        mock_queue = MagicMock()
        mock_queue.empty.return_value = False
        mock_queue.get.return_value = {"status": "ok", "result": {"valid": True}}
        
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        mock_process.join.return_value = None
        
        mock_ctx = MagicMock()
        mock_ctx.Queue.return_value = mock_queue
        mock_ctx.Process.return_value = mock_process
        mock_context.return_value = mock_ctx
        
        result = execute_validator(script, data)
        assert result["valid"] is True

    @patch_module.object(validator_service_module, 'cloudwatch', autospec=True)
    @patch('src.services.validator_service.get_context')
    def test_execute_validator_timeout(self, mock_context, mock_cloudwatch):
        """Test executing validator with timeout"""
        from src.services.validator_service import execute_validator
        
        script = "def validate(data): import time; time.sleep(10); return True"
        data = {"name": "test-pkg"}
        
        mock_queue = MagicMock()
        mock_queue.empty.return_value = True
        
        mock_process = MagicMock()
        # After join, is_alive should return True to simulate timeout
        mock_process.is_alive.return_value = True
        mock_process.join.return_value = None
        mock_process.terminate.return_value = None
        
        mock_ctx = MagicMock()
        mock_ctx.Queue.return_value = mock_queue
        mock_ctx.Process.return_value = mock_process
        mock_context.return_value = mock_ctx
        
        result = execute_validator(script, data)
        assert result["valid"] is False
        # Error message contains "timed out" or "timeout"
        assert "timed out" in result["error"].lower() or "timeout" in result["error"].lower()

    @patch_module.object(validator_service_module, 'dynamodb', autospec=True)
    def test_log_download_event_success(self, mock_dynamodb):
        """Test logging download event successfully"""
        from src.services.validator_service import log_download_event
        
        mock_table = MagicMock()
        mock_table.put_item.return_value = None
        mock_dynamodb.Table.return_value = mock_table
        
        log_download_event(
            "test-pkg", "1.0.0", "user123", "allowed", "Test reason"
        )
        
        mock_table.put_item.assert_called_once()

    @patch_module.object(validator_service_module, 'dynamodb', autospec=True)
    def test_log_download_event_exception(self, mock_dynamodb):
        """Test logging download event with exception"""
        from src.services.validator_service import log_download_event
        
        mock_table = MagicMock()
        mock_table.put_item.side_effect = Exception("DB error")
        mock_dynamodb.Table.return_value = mock_table
        
        # Should not raise exception
        log_download_event(
            "test-pkg", "1.0.0", "user123", "allowed", "Test reason"
        )


class TestValidatorServiceEndpoints:
    """Test validator service API endpoints"""

    @pytest.mark.asyncio
    @patch('boto3.resource')
    @patch('boto3.client')
    async def test_health_check(self, mock_client, mock_resource):
        """Test health check endpoint"""
        from src.services.validator_service import health_check
        
        result = await health_check()
        assert result.status == "healthy"
        assert "timestamp" in result.dict()

    @pytest.mark.asyncio
    @patch('src.services.validator_service.get_package_metadata')
    @patch('src.services.validator_service.log_download_event')
    async def test_validate_package_not_found(self, mock_log, mock_get_meta):
        """Test validate package when not found"""
        from src.services.validator_service import validate_package, ValidationRequest
        from fastapi import HTTPException
        
        mock_get_meta.return_value = None
        
        request = ValidationRequest(
            pkg_name="nonexistent",
            version="1.0.0",
            user_id="user123",
            user_groups=[]
        )
        
        with pytest.raises(HTTPException):
            await validate_package(request)

    @pytest.mark.asyncio
    @patch('src.services.validator_service.get_package_metadata')
    @patch('src.services.validator_service.log_download_event')
    async def test_validate_package_non_sensitive(self, mock_log, mock_get_meta):
        """Test validate package for non-sensitive package"""
        from src.services.validator_service import validate_package, ValidationRequest
        
        mock_get_meta.return_value = {
            "is_sensitive": False,
            "name": "test-pkg"
        }
        
        request = ValidationRequest(
            pkg_name="test-pkg",
            version="1.0.0",
            user_id="user123",
            user_groups=[]
        )
        
        result = await validate_package(request)
        assert result.allowed is True

    @pytest.mark.asyncio
    @patch('src.services.validator_service.get_package_metadata')
    @patch('src.services.validator_service.get_validator_script')
    @patch('src.services.validator_service.execute_validator')
    @patch('src.services.validator_service.log_download_event')
    async def test_validate_package_with_validator(self, mock_log, mock_execute, mock_get_script, mock_get_meta):
        """Test validate package with validator script"""
        from src.services.validator_service import validate_package, ValidationRequest
        
        mock_get_meta.return_value = {
            "is_sensitive": True,
            "allowed_groups": ["Group_106"],
            "name": "test-pkg"
        }
        mock_get_script.return_value = "def validate(data): return {'valid': True}"
        mock_execute.return_value = {"valid": True, "result": {"score": 0.9}}
        
        request = ValidationRequest(
            pkg_name="test-pkg",
            version="1.0.0",
            user_id="user123",
            user_groups=["Group_106"]
        )
        
        result = await validate_package(request)
        assert result.allowed is True
        assert result.validation_result is not None

    @pytest.mark.asyncio
    @patch_module.object(validator_service_module, 'dynamodb', autospec=True)
    async def test_get_user_history_success(self, mock_dynamodb):
        """Test getting user history successfully"""
        from src.services.validator_service import get_user_history
        
        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"event_id": "event1", "pkg_name": "pkg1"},
                {"event_id": "event2", "pkg_name": "pkg2"}
            ]
        }
        mock_dynamodb.Table.return_value = mock_table
        
        result = await get_user_history("user123", limit=50)
        assert result["user_id"] == "user123"
        assert len(result["downloads"]) == 2

    @pytest.mark.asyncio
    @patch_module.object(validator_service_module, 'dynamodb', autospec=True)
    async def test_get_user_history_exception(self, mock_dynamodb):
        """Test getting user history with exception"""
        from src.services.validator_service import get_user_history
        from fastapi import HTTPException
        
        mock_table = MagicMock()
        mock_table.query.side_effect = Exception("DB error")
        mock_dynamodb.Table.return_value = mock_table
        
        with pytest.raises(HTTPException):
            await get_user_history("user123")

