"""
Unit tests for artifacts routes
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime


@pytest.fixture
def client():
    """Create a test client"""
    from src.index import app
    return TestClient(app)


class TestArtifactsRoutes:
    """Test artifact management routes"""
    
    def test_list_artifacts(self, client):
        """Test listing artifacts"""
        from src.routes.system import _INMEM_DB
        
        # Set up test data
        _INMEM_DB["artifacts"] = [{"id": "1", "name": "test", "type": "model"}]
        
        try:
            response = client.get("/api/artifacts")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
        finally:
            # Clean up
            _INMEM_DB["artifacts"] = []
    
    def test_get_artifact_by_id(self, client):
        """Test getting artifact by ID"""
        from src.routes.system import _INMEM_DB
        
        # Set up test data
        _INMEM_DB["artifacts"] = [{"id": "1", "name": "test", "type": "model"}]
        
        try:
            response = client.get("/api/artifacts/1")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "1"
        finally:
            # Clean up
            _INMEM_DB["artifacts"] = []
    
    def test_get_artifact_by_id_not_found(self, client):
        """Test getting non-existent artifact"""
        from src.routes.system import _INMEM_DB
        
        # Ensure empty
        _INMEM_DB["artifacts"] = []
        
        response = client.get("/api/artifacts/999")
        assert response.status_code == 404
    
    def test_get_artifact_by_name(self, client):
        """Test getting artifact by name"""
        from src.routes.system import _INMEM_DB
        
        # Set up test data
        _INMEM_DB["artifacts"] = [{"id": "1", "name": "test-model", "type": "model"}]
        
        try:
            response = client.get("/api/artifacts/by-name/test-model")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert data[0]["name"] == "test-model"
        finally:
            # Clean up
            _INMEM_DB["artifacts"] = []
    
    def test_ingest_artifact(self, client):
        """Test ingesting an artifact"""
        from src.routes.system import _INMEM_DB
        
        # Start with empty
        _INMEM_DB["artifacts"] = []
        
        artifact = {
            "id": "1",
            "name": "test-model",
            "type": "model",
            "version": "1.0.0"
        }
        
        try:
            response = client.put("/api/ingest", json=artifact)
            assert response.status_code == 200
            data = response.json()
            assert "ingested" in data
            assert data["ingested"] == 1
        finally:
            # Clean up
            _INMEM_DB["artifacts"] = []
    
    def test_ingest_multiple_artifacts(self, client):
        """Test ingesting multiple artifacts"""
        from src.routes.system import _INMEM_DB
        
        # Start with empty
        _INMEM_DB["artifacts"] = []
        
        artifacts = [
            {"id": "1", "name": "model1", "type": "model"},
            {"id": "2", "name": "model2", "type": "model"}
        ]
        
        try:
            response = client.put("/api/ingest", json=artifacts)
            assert response.status_code == 200
            data = response.json()
            assert data["ingested"] == 2
        finally:
            # Clean up
            _INMEM_DB["artifacts"] = []

