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


class TestArtifactsPydanticSerialization:
    """Test Pydantic model serialization paths"""

    def test_ingest_with_pydantic_model_instance(self, client):
        """Test ingesting using Pydantic model instance directly"""
        from src.routes.artifacts import Artifact, ArtifactType
        
        artifact = Artifact(
            id="pydantic-test-1",
            name="pydantic-model",
            type=ArtifactType.model,
            version="1.0.0",
            description="Test with Pydantic model"
        )
        
        # Call the endpoint function directly to test model_dump path
        from src.routes.artifacts import ingest
        result = ingest(artifact)
        assert result["ingested"] == 1
        
        # Verify it was stored
        response = client.get("/api/artifacts/pydantic-test-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pydantic-test-1"

    def test_ingest_with_datetime_object(self, client):
        """Test ingesting with datetime object in Pydantic model"""
        from src.routes.artifacts import Artifact, ArtifactType
        from datetime import datetime, UTC
        
        artifact = Artifact(
            id="datetime-test-1",
            name="datetime-model",
            type=ArtifactType.model,
            version="1.0.0",
            created_at=datetime.now(UTC)
        )
        
        from src.routes.artifacts import ingest
        result = ingest(artifact)
        assert result["ingested"] == 1
        
        # Verify datetime was serialized
        response = client.get("/api/artifacts/datetime-test-1")
        assert response.status_code == 200
        data = response.json()
        assert "created_at" in data
        assert isinstance(data["created_at"], str)  # Should be ISO string

    def test_ingest_dict_with_datetime(self, client):
        """Test ingesting dict with datetime object"""
        from datetime import datetime, UTC
        
        payload = {
            "id": "dict-datetime-1",
            "name": "dict-datetime-model",
            "type": "model",
            "version": "1.0.0",
            "created_at": datetime.now(UTC)
        }
        
        from src.routes.artifacts import ingest
        result = ingest(payload)
        assert result["ingested"] == 1


class TestArtifactsDirectFunctionCalls:
    """Test route handler functions directly for coverage"""

    def test_ingest_function_direct(self):
        """Test ingest function directly"""
        from src.routes.artifacts import ingest
        from src.routes.system import _INMEM_DB
        
        # Clear artifacts
        _INMEM_DB["artifacts"] = []
        
        payload = {
            "id": "direct-test-1",
            "name": "direct-model",
            "type": "model",
            "version": "1.0.0"
        }
        
        result = ingest(payload)
        assert result["ingested"] == 1
        assert len(_INMEM_DB["artifacts"]) == 1

    def test_list_artifacts_function_direct(self):
        """Test list_artifacts function directly"""
        from src.routes.artifacts import list_artifacts
        from src.routes.system import _INMEM_DB
        
        _INMEM_DB["artifacts"] = [
            {"id": "test-1", "name": "model-1"},
            {"id": "test-2", "name": "model-2"}
        ]
        
        result = list_artifacts()
        assert isinstance(result, list)
        assert len(result) == 2

    def test_by_name_function_direct_found(self):
        """Test by_name function directly when found"""
        from src.routes.artifacts import by_name
        from src.routes.system import _INMEM_DB
        
        _INMEM_DB["artifacts"] = [
            {"id": "test-1", "name": "test-model"},
            {"id": "test-2", "name": "test-model"},
            {"id": "test-3", "name": "other-model"}
        ]
        
        result = by_name("test-model")
        assert isinstance(result, list)
        assert len(result) == 2

    def test_by_name_function_direct_not_found(self):
        """Test by_name function directly when not found"""
        from src.routes.artifacts import by_name
        from src.routes.system import _INMEM_DB
        from fastapi import HTTPException
        
        _INMEM_DB["artifacts"] = []
        
        with pytest.raises(HTTPException) as exc_info:
            by_name("non-existent")
        
        assert exc_info.value.status_code == 404

    def test_by_id_function_direct_found(self):
        """Test by_id function directly when found"""
        from src.routes.artifacts import by_id
        from src.routes.system import _INMEM_DB
        
        _INMEM_DB["artifacts"] = [
            {"id": "test-1", "name": "model-1"},
            {"id": "test-2", "name": "model-2"}
        ]
        
        result = by_id("test-1")
        assert result["id"] == "test-1"
        assert result["name"] == "model-1"

    def test_by_id_function_direct_not_found(self):
        """Test by_id function directly when not found"""
        from src.routes.artifacts import by_id
        from src.routes.system import _INMEM_DB
        from fastapi import HTTPException
        
        _INMEM_DB["artifacts"] = []
        
        with pytest.raises(HTTPException) as exc_info:
            by_id("non-existent")
        
        assert exc_info.value.status_code == 404
