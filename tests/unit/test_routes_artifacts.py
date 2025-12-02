"""
Unit tests for artifacts routes
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create a test app with artifacts router"""
    from src.routes.artifacts import router
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create a test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_db():
    """Reset the in-memory database before and after each test"""
    from src.routes.system import _INMEM_DB

    # Store original state for safety (defensive copy)
    original_artifacts = _INMEM_DB.get("artifacts", []).copy()

    # Reset before test
    _INMEM_DB["artifacts"] = []

    try:
        yield
    finally:
        # Always reset after test, even if test fails
        # This ensures complete isolation between tests
        _INMEM_DB["artifacts"] = []


class TestArtifactsIngest:
    """Test PUT /api/ingest endpoint"""

    def test_ingest_single_artifact(self, client):
        """Test ingesting a single artifact"""
        payload = {
            "id": "test-id-1",
            "name": "test-model",
            "type": "model",
            "version": "1.0.0"
        }
        response = client.put("/api/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 1

    def test_ingest_multiple_artifacts(self, client):
        """Test ingesting multiple artifacts"""
        payload = [
            {
                "id": "test-id-1",
                "name": "test-model-1",
                "type": "model",
                "version": "1.0.0"
            },
            {
                "id": "test-id-2",
                "name": "test-model-2",
                "type": "model",
                "version": "2.0.0"
            }
        ]
        response = client.put("/api/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 2

    def test_ingest_duplicate_id(self, client):
        """Test ingesting artifact with duplicate ID"""
        payload1 = {
            "id": "test-id-1",
            "name": "test-model-1",
            "type": "model",
            "version": "1.0.0"
        }
        payload2 = {
            "id": "test-id-1",
            "name": "test-model-2",
            "type": "model",
            "version": "2.0.0"
        }
        
        # First ingestion
        response1 = client.put("/api/ingest", json=payload1)
        assert response1.status_code == 200
        assert response1.json()["ingested"] == 1
        
        # Second ingestion with same ID
        response2 = client.put("/api/ingest", json=payload2)
        assert response2.status_code == 200
        assert response2.json()["ingested"] == 0  # Duplicate not ingested

    def test_ingest_with_datetime(self, client):
        """Test ingesting artifact with datetime field"""
        payload = {
            "id": "test-id-1",
            "name": "test-model",
            "type": "model",
            "version": "1.0.0",
            "created_at": "2024-01-01T00:00:00"
        }
        response = client.put("/api/ingest", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ingested"] == 1
        
        # Verify artifact was stored
        list_response = client.get("/api/artifacts")
        artifacts = list_response.json()
        assert len(artifacts) == 1
        assert artifacts[0]["id"] == "test-id-1"
        assert "created_at" in artifacts[0]

    def test_ingest_different_types(self, client):
        """Test ingesting artifacts of different types"""
        payload = [
            {
                "id": "model-1",
                "name": "test-model",
                "type": "model",
                "version": "1.0.0"
            },
            {
                "id": "dataset-1",
                "name": "test-dataset",
                "type": "dataset",
                "version": "1.0.0"
            },
            {
                "id": "code-1",
                "name": "test-code",
                "type": "code",
                "version": "1.0.0"
            }
        ]
        response = client.put("/api/ingest", json=payload)
        assert response.status_code == 200
        assert response.json()["ingested"] == 3


class TestArtifactsList:
    """Test GET /api/artifacts endpoint"""

    def test_list_artifacts_empty(self, client):
        """Test listing artifacts when database is empty"""
        response = client.get("/api/artifacts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_list_artifacts_with_items(self, client):
        """Test listing artifacts with items"""
        # First ingest some artifacts
        payload = [
            {
                "id": "test-id-1",
                "name": "test-model-1",
                "type": "model",
                "version": "1.0.0"
            },
            {
                "id": "test-id-2",
                "name": "test-model-2",
                "type": "model",
                "version": "2.0.0"
            }
        ]
        client.put("/api/ingest", json=payload)
        
        # List artifacts
        response = client.get("/api/artifacts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "test-id-1"
        assert data[1]["id"] == "test-id-2"


class TestArtifactsByName:
    """Test GET /api/artifacts/by-name/{name} endpoint"""

    def test_by_name_found(self, client):
        """Test finding artifacts by name when found"""
        # Ingest artifacts
        payload = [
            {
                "id": "test-id-1",
                "name": "test-model",
                "type": "model",
                "version": "1.0.0"
            },
            {
                "id": "test-id-2",
                "name": "test-model",
                "type": "model",
                "version": "2.0.0"
            },
            {
                "id": "test-id-3",
                "name": "other-model",
                "type": "model",
                "version": "1.0.0"
            }
        ]
        client.put("/api/ingest", json=payload)
        
        # Find by name
        response = client.get("/api/artifacts/by-name/test-model")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all(a["name"] == "test-model" for a in data)

    def test_by_name_not_found(self, client):
        """Test finding artifacts by name when not found"""
        # Ingest some artifacts
        payload = {
            "id": "test-id-1",
            "name": "test-model",
            "type": "model",
            "version": "1.0.0"
        }
        client.put("/api/ingest", json=payload)
        
        # Try to find non-existent name
        response = client.get("/api/artifacts/by-name/non-existent")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not found"

    def test_by_name_empty_database(self, client):
        """Test finding artifacts by name when database is empty"""
        response = client.get("/api/artifacts/by-name/test-model")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Not found"


class TestArtifactsById:
    """Test GET /api/artifacts/{artifact_id} endpoint"""

    def test_by_id_found(self, client):
        """Test finding artifact by ID when found"""
        # Ingest artifact
        payload = {
            "id": "test-id-1",
            "name": "test-model",
            "type": "model",
            "version": "1.0.0",
            "description": "Test description"
        }
        client.put("/api/ingest", json=payload)
        
        # Find by ID
        response = client.get("/api/artifacts/test-id-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id-1"
        assert data["name"] == "test-model"
        assert data["type"] == "model"
        assert data["description"] == "Test description"

    def test_by_id_not_found(self, client):
        """Test finding artifact by ID when not found"""
        # Ingest some artifacts
        payload = {
            "id": "test-id-1",
            "name": "test-model",
            "type": "model",
            "version": "1.0.0"
        }
        client.put("/api/ingest", json=payload)
        
        # Try to find non-existent ID
        response = client.get("/api/artifacts/non-existent-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Not found"

    def test_by_id_empty_database(self, client):
        """Test finding artifact by ID when database is empty"""
        response = client.get("/api/artifacts/test-id-1")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Not found"
