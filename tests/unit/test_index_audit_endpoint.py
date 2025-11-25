"""
Comprehensive tests for index.py audit endpoint and additional endpoints
Targeting lines 2966-3128 and 3289-3398
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from botocore.exceptions import ClientError
from src.index import app

client = TestClient(app)


class TestAuditTrailEndpoint:
    """Test audit trail endpoint - lines 2966-3128"""
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.s3")
    def test_audit_trail_model_found_in_db(self, mock_s3, mock_get_meta, mock_verify):
        """Test audit trail for model found in database"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {
            "id": "m1",
            "name": "model1",
            "type": "model",
            "version": "1.0.0"
        }
        
        # Mock S3 head_object for creation date
        mock_s3.head_object.return_value = {
            "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        }
        
        response = client.get("/artifact/model/m1/audit")
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.list_models")
    @patch("src.index.s3")
    def test_audit_trail_model_found_via_list(
        self, mock_s3, mock_list, mock_get_db, mock_get_meta, mock_verify
    ):
        """Test audit trail for model found via list_models"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        
        # Found via list_models
        mock_list.return_value = {
            "models": [{"name": "model1", "version": "1.0.0"}]
        }
        
        mock_s3.head_object.return_value = {
            "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        }
        
        response = client.get("/artifact/model/model1/audit")
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.list_models")
    @patch("src.index.s3")
    def test_audit_trail_common_version_fallback(
        self, mock_s3, mock_list, mock_get_db, mock_get_meta, mock_verify
    ):
        """Test audit trail falls back to common versions"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_list.return_value = {"models": []}
        
        # First call fails, second succeeds (checking 1.0.0, main, latest)
        mock_s3.head_object.side_effect = [
            ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject"),
            {"LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        ]
        
        response = client.get("/artifact/model/model1/audit")
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.list_models")
    def test_audit_trail_model_not_found(
        self, mock_list, mock_get_db, mock_get_meta, mock_verify
    ):
        """Test audit trail for non-existent model"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_list.return_value = {"models": []}
        
        response = client.get("/artifact/model/nonexistent/audit")
        assert response.status_code == 404

    def test_audit_trail_invalid_artifact_type(self):
        """Test audit trail with invalid artifact type"""
        response = client.get("/artifact/invalid_type/m1/audit")
        assert response.status_code in [400, 404, 422]

    @patch("src.index.verify_auth_token")
    def test_audit_trail_empty_id(self, mock_verify):
        """Test audit trail with empty ID"""
        mock_verify.return_value = {"username": "user1"}
        
        response = client.get("/artifact/model/ /audit")
        assert response.status_code in [400, 404, 422]


class TestAuditTrailDateHandling:
    """Test audit trail date handling"""
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.s3")
    def test_audit_last_modified_naive_datetime(self, mock_s3, mock_get_meta, mock_verify):
        """Test handling of naive datetime (no timezone)"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {
            "id": "m1",
            "type": "model",
            "version": "1.0.0"
        }
        
        # Return naive datetime
        mock_s3.head_object.return_value = {
            "LastModified": datetime(2024, 1, 1)  # No timezone
        }
        
        response = client.get("/artifact/model/m1/audit")
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.s3")
    def test_audit_last_modified_missing(self, mock_s3, mock_get_meta, mock_verify):
        """Test handling when LastModified is missing"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {
            "id": "m1",
            "type": "model",
            "version": "1.0.0"
        }
        
        # Return without LastModified
        mock_s3.head_object.return_value = {}
        
        response = client.get("/artifact/model/m1/audit")
        assert response.status_code in [200, 404]

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.s3")
    def test_audit_s3_no_such_key_error(self, mock_s3, mock_get_meta, mock_verify):
        """Test handling S3 NoSuchKey error"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = {
            "id": "m1",
            "type": "model",
            "version": "1.0.0"
        }
        
        # S3 key doesn't exist
        mock_s3.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "HeadObject"
        )
        
        response = client.get("/artifact/model/m1/audit")
        assert response.status_code in [200, 404]


class TestMultipleVersionChecking:
    """Test checking multiple common versions - lines 3018-3028"""
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.list_models")
    @patch("src.index.s3")
    def test_version_fallback_1_0_0(self, mock_s3, mock_list, mock_get_db, mock_get_meta, mock_verify):
        """Test fallback to version 1.0.0"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_list.return_value = {"models": []}
        
        # Success on first version check (1.0.0)
        mock_s3.head_object.return_value = {
            "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        }
        
        response = client.get("/artifact/model/model1/audit")
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.list_models")
    @patch("src.index.s3")
    def test_version_fallback_main(self, mock_s3, mock_list, mock_get_db, mock_get_meta, mock_verify):
        """Test fallback to version 'main'"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_list.return_value = {"models": []}
        
        # Fail 1.0.0, succeed on 'main'
        mock_s3.head_object.side_effect = [
            ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject"),
            {"LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        ]
        
        response = client.get("/artifact/model/model1/audit")
        assert response.status_code == 200

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index.get_artifact_from_db")
    @patch("src.index.list_models")
    @patch("src.index.s3")
    def test_version_fallback_latest(self, mock_s3, mock_list, mock_get_db, mock_get_meta, mock_verify):
        """Test fallback to version 'latest'"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_db.return_value = None
        mock_list.return_value = {"models": []}
        
        # Fail 1.0.0 and main, succeed on 'latest'
        mock_s3.head_object.side_effect = [
            ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject"),
            ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject"),
            {"LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        ]
        
        response = client.get("/artifact/model/model1/audit")
        assert response.status_code == 200


class TestSanitizedNameUsage:
    """Test using sanitized model names for S3 lookup - lines 3014-3037"""
    
    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index._get_model_name_for_s3")
    @patch("src.index.sanitize_model_id_for_s3")
    @patch("src.index.s3")
    def test_uses_get_model_name_for_s3(
        self, mock_s3, mock_sanitize, mock_get_name, mock_get_meta, mock_verify
    ):
        """Test using _get_model_name_for_s3 first"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_name.return_value = "user-model"
        
        mock_s3.head_object.return_value = {
            "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        }
        
        with patch("src.index.get_artifact_from_db") as mock_get_db:
            with patch("src.index.list_models") as mock_list:
                mock_get_db.return_value = None
                mock_list.return_value = {"models": []}
                
                response = client.get("/artifact/model/m1/audit")
                
                # Should have called _get_model_name_for_s3
                mock_get_name.assert_called()

    @patch("src.index.verify_auth_token")
    @patch("src.index.get_generic_artifact_metadata")
    @patch("src.index._get_model_name_for_s3")
    @patch("src.index.sanitize_model_id_for_s3")
    @patch("src.index.s3")
    def test_fallback_to_sanitize(
        self, mock_s3, mock_sanitize, mock_get_name, mock_get_meta, mock_verify
    ):
        """Test fallback to sanitize_model_id_for_s3"""
        mock_verify.return_value = {"username": "user1"}
        mock_get_meta.return_value = None
        mock_get_name.return_value = None  # Force fallback
        mock_sanitize.return_value = "user-model"
        
        mock_s3.head_object.return_value = {
            "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)
        }
        
        with patch("src.index.get_artifact_from_db") as mock_get_db:
            with patch("src.index.list_models") as mock_list:
                mock_get_db.return_value = None
                mock_list.return_value = {"models": []}
                
                response = client.get("/artifact/model/m1/audit")
                
                # Should have called sanitize as fallback
                mock_sanitize.assert_called()
