import pytest
from fastapi.testclient import TestClient
from src.index import app

pytestmark = pytest.mark.integration

class TestRateEndpoint:
    """Integration tests for the rate endpoint."""
    
    def test_calls_real_python_scorer_and_returns_data(self):
        """Test that the rate endpoint calls real Python scorer and returns data."""
        client = TestClient(app)
        
        response = client.post(
            "/api/registry/models/demo/rate",
            json={"target": "https://github.com/pallets/flask"},
            headers={"Content-Type": "application/json"},
        )
        
        assert response.status_code in (200, 201, 202, 204), response.text
        data = response.json()
        assert isinstance(data, dict)
        assert "data" in data  # tighten further to your contract if desired

if __name__ == "__main__":
    pytest.main([__file__])
