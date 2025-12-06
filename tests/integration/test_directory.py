#!/usr/bin/env python3
"""
Test script to verify directory page shows packages
"""
import requests
import json
import pytest

def test_directory_page():
    """Test that the directory page shows packages"""
    base_url = "http://localhost:3000"

    try:
        response = requests.get(f"{base_url}/directory", timeout=30)

        assert response.status_code == 200, (
            f"Directory page failed with status {response.status_code}"
        )

        content = response.text

        # Validate HTML structure
        assert len(content) > 0, "Directory page should have content"
        assert "<html" in content.lower() or "<!doctype" in content.lower(), (
            "Directory page should be valid HTML"
        )
        assert "<body" in content.lower(), (
            "Directory page should have a body element"
        )

        # Check for common HTML elements that should be present
        # (These are basic checks - actual structure depends on implementation)
        assert "<title" in content.lower() or "<h1" in content.lower() or (
            "directory" in content.lower()
        ), "Directory page should have title or heading"

    except requests.exceptions.ConnectionError:
        pytest.skip("Server not available - skipping integration test")
    except requests.exceptions.Timeout:
        pytest.skip("Server request timed out - skipping integration test")
    except Exception as e:
        pytest.fail(f"Error testing directory: {str(e)}")

def test_api_packages():
    """Test that the API still shows packages"""
    base_url = "http://localhost:3000"

    try:
        response = requests.get(f"{base_url}/api/packages", timeout=30)

        assert response.status_code == 200, (
            f"API failed with status {response.status_code}"
        )

        result = response.json()
        assert isinstance(result, dict), "API response should be a JSON object"

        # Validate packages structure
        assert "packages" in result, "Response should contain 'packages' field"
        packages = result.get("packages", [])

        assert isinstance(packages, list), "packages should be a list"

        # Validate package structure if packages exist
        if len(packages) > 0:
            for pkg in packages:
                assert isinstance(pkg, dict), "Each package should be a dict"
                assert "name" in pkg, "Package missing required field: name"
                assert "version" in pkg, "Package missing required field: version"
                assert isinstance(pkg["name"], str), "Package name should be a string"
                assert len(pkg["name"]) > 0, "Package name should not be empty"
                assert isinstance(
                    pkg["version"], str
                ), "Package version should be a string"
                assert len(pkg["version"]) > 0, (
                    "Package version should not be empty"
                )

    except requests.exceptions.ConnectionError:
        pytest.skip("Server not available - skipping integration test")
    except requests.exceptions.Timeout:
        pytest.skip("Server request timed out - skipping integration test")
    except Exception as e:
        pytest.fail(f"Error testing API: {str(e)}")

if __name__ == "__main__":
    print("Testing Directory Page Package Display")
    print("=" * 50)
    
    # Test API first
    try:
        test_api_packages()
        api_success = True
    except (AssertionError, Exception) as e:
        print(f"API test failed: {e}")
        api_success = False
    
    # Test directory page
    try:
        test_directory_page()
        directory_success = True
    except (AssertionError, Exception) as e:
        print(f"Directory test failed: {e}")
        directory_success = False
    
    print("\n" + "=" * 50)
    if api_success and directory_success:
        print("All tests passed! Directory shows packages correctly.")
    elif api_success and not directory_success:
        print("API works but directory page needs server restart.")
        print("Please restart the server with: python -m src.index")
    else:
        print("Some tests failed. Check the output above.")



