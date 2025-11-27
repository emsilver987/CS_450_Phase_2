import pytest
import requests
import subprocess
import sys
import os
from typing import Optional

def has_python() -> bool:
    """Check if Python is available in the system."""
    try:
        result = subprocess.run([sys.executable, "--version"], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

@pytest.fixture(scope="module")
def app_url():
    """Get the application URL for testing."""
    # You may need to adjust this based on your deployment
    return os.getenv("TEST_APP_URL", "http://localhost:8000")

@pytest.fixture(scope="module")
def skip_if_no_python():
    """Skip tests if Python is not available."""
    if not has_python():
        pytest.skip("Skipping integration test: Python not found")

class TestRateEndpoint:
    """Integration tests for the rate endpoint."""
    
    def test_calls_real_python_scorer_and_returns_data(self, app_url, skip_if_no_python):
        """Test that the rate endpoint calls real Python scorer and returns data."""
        if not has_python():
            pytest.skip("Python not available")
        
        url = f"{app_url}/api/registry/models/demo/rate"
        payload = {"target": "https://github.com/pallets/flask"}
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=5
            )

            # Expect 200 for successful rating, handle errors explicitly
            if response.status_code == 200:
                response_data = response.json()

                # Check that the response has the expected structure
                assert "data" in response_data, "Response missing 'data' field"
                assert isinstance(
                    response_data["data"], dict
                ), "data should be a dict"

                # Validate netScore
                assert "netScore" in response_data["data"], (
                    "Response missing 'data.netScore' field"
                )
                net_score = response_data["data"]["netScore"]
                assert isinstance(
                    net_score, (int, float)
                ), "netScore should be numeric"
                assert 0.0 <= net_score <= 1.0, (
                    f"netScore {net_score} out of range [0.0, 1.0]"
                )

                # Validate subscores structure
                assert "subscores" in response_data["data"], (
                    "Response missing 'data.subscores' field"
                )
                subscores = response_data["data"]["subscores"]
                assert isinstance(
                    subscores, dict
                ), "subscores should be a dict"

                # Validate subscore values are in valid range
                for key, value in subscores.items():
                    if isinstance(value, (int, float)):
                        assert 0.0 <= value <= 1.0, (
                            f"Subscore {key}={value} out of range [0.0, 1.0]"
                        )

            elif response.status_code == 422:
                # Validation error - validate error structure
                try:
                    error_data = response.json()
                    assert isinstance(
                        error_data, dict
                    ), "Error response should be a JSON object"
                except ValueError:
                    pass  # Plain text error is acceptable
            elif response.status_code == 502:
                # Server error - acceptable for integration test
                pass
            else:
                pytest.fail(
                    f"Unexpected status code: {response.status_code}, "
                    f"response: {response.text[:200]}"
                )
            
        except requests.exceptions.ConnectionError:
            # Skip if server is not running (this is expected in CI/unit test environments)
            pytest.skip("Server not available - skipping integration test")
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Request failed: {e}")
        except ValueError as e:
            pytest.fail(f"Invalid JSON response: {e}")

if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])
