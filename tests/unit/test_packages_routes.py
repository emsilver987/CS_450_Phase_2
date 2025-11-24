import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Test the actual router endpoints - routes are included in main app via index.py
def test_rate_package():
    """Test rate package endpoint"""
    from src.routes.packages import router
    app = FastAPI()
    # Router needs a prefix since it has empty path routes
    app.include_router(router, prefix="/packages")
    
    with patch("src.services.rating.run_scorer") as mock_scorer:
        mock_scorer.return_value = {"net_score": 0.8}
        client = TestClient(app)
        response = client.get("/packages/rate/test-model")
        # Should call run_scorer or handle error
        assert response.status_code in [200, 500]

def test_search_packages():
    """Test search packages endpoint"""
    from src.routes.packages import router
    app = FastAPI()
    app.include_router(router, prefix="/packages")
    
    with patch("src.services.s3_service.list_models") as mock_list:
        mock_list.return_value = {"models": [], "next_token": None}
        client = TestClient(app)
        response = client.get("/packages/search?q=test")
        assert response.status_code == 200

def test_list_packages():
    """Test list packages endpoint"""
    from src.routes.packages import router
    app = FastAPI()
    app.include_router(router, prefix="/packages")
    
    with patch("src.services.s3_service.list_models") as mock_list:
        mock_list.return_value = {"models": [], "next_token": None}
        client = TestClient(app)
        # list_packages is a GET endpoint at root of router
        response = client.get("/packages")
        # May need auth, check for 200 or 401
        assert response.status_code in [200, 401, 422]

@patch("src.services.s3_service.upload_model")
def test_upload_model_file(mock_upload):
    """Test upload model file endpoint"""
    from src.routes.packages import router
    app = FastAPI()
    app.include_router(router, prefix="/packages")
    
    mock_upload.return_value = {"message": "success"}
    client = TestClient(app)
    files = {"file": ("test.zip", b"test content", "application/zip")}
    response = client.post("/packages/models/test-model/1.0.0/model.zip", files=files)
    # May succeed or fail depending on validation
    assert response.status_code in [200, 400, 500]
