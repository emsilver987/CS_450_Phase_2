"""
Unit tests for artifacts routes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime


@pytest.fixture
def client():
    """Create a test client"""
    from src.index import app
    return TestClient(app)


class TestArtifactsRoutes:
    """Test artifact management routes"""
    
    @patch('src.routes.artifacts._INMEM_DB')
    def test_list_artifacts(self, mock_db, client):
        """Test listing artifacts"""
        mock_db.get.return_value = [
            {"id": "1", "name": "test", "type": "model"}
        ]
        
        response = client.get("/api/artifacts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    @patch('src.routes.artifacts._INMEM_DB')
    def test_get_artifact_by_id(self, mock_db, client):
        """Test getting artifact by ID"""
        mock_db.get.return_value = [
            {"id": "1", "name": "test", "type": "model"}
        ]
        
        response = client.get("/api/artifacts/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "1"
    
    @patch('src.routes.artifacts._INMEM_DB')
    def test_get_artifact_by_id_not_found(self, mock_db, client):
        """Test getting non-existent artifact"""
        mock_db.get.return_value = []
        
        response = client.get("/api/artifacts/999")
        assert response.status_code == 404
    
    @patch('src.routes.artifacts._INMEM_DB')
    def test_get_artifact_by_name(self, mock_db, client):
        """Test getting artifact by name"""
        mock_db.get.return_value = [
            {"id": "1", "name": "test-model", "type": "model"}
        ]
        
        response = client.get("/api/artifacts/by-name/test-model")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["name"] == "test-model"
    
    @patch('src.routes.artifacts._INMEM_DB')
    def test_ingest_artifact(self, mock_db, client):
        """Test ingesting an artifact"""
        mock_db.get.return_value = []
        mock_db.setdefault.return_value = []
        
        artifact = {
            "id": "1",
            "name": "test-model",
            "type": "model",
            "version": "1.0.0"
        }
        
        response = client.put("/api/ingest", json=artifact)
        assert response.status_code == 200
        data = response.json()
        assert "ingested" in data
    
    @patch('src.routes.artifacts._INMEM_DB')
    def test_ingest_multiple_artifacts(self, mock_db, client):
        """Test ingesting multiple artifacts"""
        mock_db.get.return_value = []
        mock_db.setdefault.return_value = []
        
        artifacts = [
            {"id": "1", "name": "model1", "type": "model"},
            {"id": "2", "name": "model2", "type": "model"}
        ]
        
        response = client.put("/api/ingest", json=artifacts)
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 2

