import pytest
import logging
from unittest.mock import patch

pytest.importorskip("httpx")
pytest.importorskip("selenium")

@pytest.fixture(scope="session", autouse=True)
def patch_watchtower():
    with patch("watchtower.CloudWatchLogHandler") as mock:
        mock.return_value.level = logging.INFO
        yield

def get_test_client(app):
    from fastapi.testclient import TestClient
    return TestClient(app)
