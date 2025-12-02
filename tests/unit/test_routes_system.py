"""
Unit tests for system routes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch


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

    def test_health_endpoint_direct(self):
        """Test health endpoint directly from router"""
        from src.routes.system import health
        result = health()
        assert result == {"status": "ok"}

    def test_tracks_endpoint_direct(self):
        """Test tracks endpoint directly from router"""
        from src.routes.system import tracks
        result = tracks()
        assert "tracks" in result
        assert isinstance(result["tracks"], list)

    @patch('src.services.auth_service.purge_tokens')
    @patch('src.services.auth_service.ensure_default_admin')
    def test_reset_post_direct(self, mock_ensure_admin, mock_purge):
        """Test POST /reset endpoint directly"""
        from src.routes.system import reset, _INMEM_DB
        
        # Add some artifacts
        _INMEM_DB["artifacts"] = [{"id": "test-1"}, {"id": "test-2"}]
        
        result = reset()
        
        assert result == {"status": "ok"}
        assert len(_INMEM_DB["artifacts"]) == 0
        mock_purge.assert_called_once()
        mock_ensure_admin.assert_called_once()

    @patch('src.services.auth_service.purge_tokens')
    @patch('src.services.auth_service.ensure_default_admin')
    def test_reset_delete_direct(self, mock_ensure_admin, mock_purge):
        """Test DELETE /reset endpoint directly"""
        from src.routes.system import reset_delete, _INMEM_DB
        
        # Add some artifacts
        _INMEM_DB["artifacts"] = [{"id": "test-1"}]
        
        result = reset_delete()
        
        assert result == {"status": "ok"}
        assert len(_INMEM_DB["artifacts"]) == 0
        mock_purge.assert_called_once()
        mock_ensure_admin.assert_called_once()

    def test_health_returns_ok(self):
        """Test health endpoint returns correct structure"""
        from src.routes.system import health
        result = health()
        assert result == {"status": "ok"}

    def test_tracks_returns_list(self):
        """Test tracks endpoint returns list of tracks"""
        from src.routes.system import tracks
        result = tracks()
        assert "tracks" in result
        assert isinstance(result["tracks"], list)
        assert len(result["tracks"]) > 0

    @patch('src.services.auth_service.purge_tokens')
    @patch('src.services.auth_service.ensure_default_admin')
    def test_reset_clears_artifacts(self, mock_ensure_admin, mock_purge):
        """Test reset clears artifacts database"""
        from src.routes.system import reset, _INMEM_DB
        
        # Set up artifacts
        _INMEM_DB["artifacts"] = [{"id": "artifact-1"}, {"id": "artifact-2"}]
        
        result = reset()
        
        assert result == {"status": "ok"}
        assert len(_INMEM_DB["artifacts"]) == 0

    @patch('src.services.auth_service.purge_tokens')
    @patch('src.services.auth_service.ensure_default_admin')
    def test_reset_delete_clears_artifacts(self, mock_ensure_admin, mock_purge):
        """Test reset_delete clears artifacts database"""
        from src.routes.system import reset_delete, _INMEM_DB
        
        # Set up artifacts
        _INMEM_DB["artifacts"] = [{"id": "artifact-1"}]
        
        result = reset_delete()
        
        assert result == {"status": "ok"}
        assert len(_INMEM_DB["artifacts"]) == 0

    def test_reset_empty_artifacts(self):
        """Test reset when artifacts list is already empty"""
        from src.routes.system import reset, _INMEM_DB

        _INMEM_DB["artifacts"] = []

        with patch('src.services.auth_service.purge_tokens'), \
             patch('src.services.auth_service.ensure_default_admin'):
            result = reset()

            assert result == {"status": "ok"}
            assert len(_INMEM_DB["artifacts"]) == 0

