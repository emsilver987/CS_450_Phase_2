"""
Unit tests for system routes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    """Create a test client"""
    from src.index import app
    return TestClient(app)


class TestSystemRoutes:
    """Test system management routes"""
    
    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "ok" in data
        assert data["ok"] is True

    def test_health_components(self, client):
        """Test health components endpoint"""
        response = client.get("/health/components")
        assert response.status_code == 200

    def test_tracks_endpoint(self, client):
        """Test tracks endpoint"""
        response = client.get("/tracks")
        assert response.status_code == 200
        data = response.json()
        assert "plannedTracks" in data
        assert isinstance(data["plannedTracks"], list)

    def test_reset_delete_requires_auth(self, client):
        """Test DELETE /reset endpoint requires authentication"""
        # Test without auth - should fail
        response = client.delete("/reset")
        assert response.status_code in [401, 403]  # Requires authentication

    @patch('src.index.verify_jwt_token')
    @patch('src.index.verify_auth_token')
    @patch('src.services.s3_service.reset_registry')
    @patch('src.services.artifact_storage.clear_all_artifacts')
    def test_reset_delete_with_auth(self, mock_clear, mock_reset, mock_auth, mock_jwt, client):
        """Test DELETE /reset endpoint with proper authentication"""
        # Mock auth to pass
        mock_auth.return_value = True
        mock_jwt.return_value = {
            "username": "ece30861defaultadminuser",
            "roles": ["admin"],
            "is_admin": True
        }
        mock_reset.return_value = {"status": "ok"}
        mock_clear.return_value = True

        response = client.delete("/reset", headers={"Authorization": "Bearer test-token"})
        # Should succeed with proper admin auth
        assert response.status_code == 200

