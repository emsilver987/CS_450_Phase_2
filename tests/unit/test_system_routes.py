"""
Tests for system.py routes
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from src.routes.system import router, _INMEM_DB


@pytest.fixture
def app():
    """Create test app"""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def reset_db():
    """Reset database before each test"""
    _INMEM_DB["artifacts"] = []
    yield
    _INMEM_DB["artifacts"] = []


class TestSystemRoutes:
    """Test system routes"""
    
    def test_health_endpoint(self, client):
        """Test health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_tracks_endpoint(self, client):
        """Test tracks endpoint"""
        response = client.get("/tracks")
        assert response.status_code == 200
        data = response.json()
        assert "tracks" in data
        assert isinstance(data["tracks"], list)
    
    @patch("src.routes.system.purge_tokens")
    @patch("src.routes.system.ensure_default_admin")
    def test_reset_post(self, mock_ensure, mock_purge, client, reset_db):
        """Test POST reset endpoint"""
        _INMEM_DB["artifacts"].append({"id": "test", "name": "test"})
        assert len(_INMEM_DB["artifacts"]) > 0
        
        response = client.post("/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(_INMEM_DB["artifacts"]) == 0
        mock_purge.assert_called_once()
        mock_ensure.assert_called_once()
    
    @patch("src.routes.system.purge_tokens")
    @patch("src.routes.system.ensure_default_admin")
    def test_reset_delete(self, mock_ensure, mock_purge, client, reset_db):
        """Test DELETE reset endpoint"""
        _INMEM_DB["artifacts"].append({"id": "test", "name": "test"})
        assert len(_INMEM_DB["artifacts"]) > 0
        
        response = client.delete("/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(_INMEM_DB["artifacts"]) == 0
        mock_purge.assert_called_once()
        mock_ensure.assert_called_once()
    
    @patch("src.routes.system.purge_tokens")
    @patch("src.routes.system.ensure_default_admin")
    def test_reset_empty_db(self, mock_ensure, mock_purge, client, reset_db):
        """Test reset with empty database"""
        assert len(_INMEM_DB["artifacts"]) == 0
        
        response = client.post("/reset")
        assert response.status_code == 200
        assert len(_INMEM_DB["artifacts"]) == 0
        mock_purge.assert_called_once()
        mock_ensure.assert_called_once()

