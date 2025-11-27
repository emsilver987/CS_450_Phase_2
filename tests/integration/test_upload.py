#!/usr/bin/env python3
"""
Test script for uploading models to the ACME Registry
"""
import requests
import json
import os
import pytest
import zipfile

def test_upload_model():
    """Test uploading a model to the registry"""
    
    # Local API endpoint
    base_url = "http://localhost:3000"
    
    # Model details
    model_id = "sample-bert-model"
    version = "1.0.0"
    
    # Path to the ZIP file
    zip_path = "test_models/sample-model.zip"
    
    if not os.path.exists(zip_path):
        pytest.skip(f"ZIP file not found at {zip_path}")
    
    # Upload endpoint
    upload_url = f"{base_url}/api/packages/models/{model_id}/versions/{version}/upload"
    
    try:
        # Read the ZIP file and get its size
        with open(zip_path, 'rb') as f:
            zip_content = f.read()
            zip_size = len(zip_content)

        # Validate ZIP file before upload
        assert zip_size > 0, "ZIP file should not be empty"
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                file_list = zf.namelist()
                assert len(file_list) > 0, "ZIP file should contain files"
        except zipfile.BadZipFile:
            pytest.fail(f"Invalid ZIP file at {zip_path}")

        # Upload the file
        with open(zip_path, 'rb') as f:
            files = {'file': ('sample-model.zip', f, 'application/zip')}
            response = requests.post(upload_url, files=files, timeout=30)

        assert response.status_code == 200, (
            f"Upload failed with status {response.status_code}: "
            f"{response.text[:200]}"
        )

        # Validate upload response structure
        result = response.json()
        assert isinstance(result, dict), "Upload response should be a JSON object"

        # Check for success indicators
        if "status" in result:
            assert isinstance(result["status"], str), "status should be a string"
        if "message" in result:
            assert isinstance(result["message"], str), (
                "message should be a string"
            )
        if "id" in result:
            assert isinstance(result["id"], str), "id should be a string"
        if "model_id" in result:
            assert result["model_id"] == model_id, (
                f"Model ID should match: expected {model_id}, "
                f"got {result['model_id']}"
            )

        # Response should indicate success
        assert (
            "status" in result or "message" in result or "id" in result
        ), "Response should indicate upload result"

    except requests.exceptions.ConnectionError:
        pytest.skip("Server not available - skipping integration test")
    except Exception as e:
        pytest.fail(f"Error during upload: {str(e)}")

def test_list_packages():
    """Test listing packages in the registry"""
    
    base_url = "http://localhost:3000"
    list_url = f"{base_url}/api/packages"
    
    try:
        response = requests.get(list_url, timeout=5)

        assert response.status_code == 200, (
            f"List failed with status {response.status_code}: "
            f"{response.text[:200]}"
        )

        result = response.json()
        assert isinstance(result, dict), "List response should be a JSON object"

        # Validate packages structure
        assert "packages" in result, "Response should contain 'packages' field"
        packages = result.get("packages", [])
        assert isinstance(packages, list), "packages should be a list"

        # Validate package structure if packages exist
        if len(packages) > 0:
            for pkg in packages:
                assert isinstance(pkg, dict), "Each package should be a dict"
                if "name" in pkg:
                    assert isinstance(
                        pkg["name"], str
                    ), "Package name should be a string"
                if "version" in pkg:
                    assert isinstance(
                        pkg["version"], str
                    ), "Package version should be a string"

    except requests.exceptions.ConnectionError:
        pytest.skip("Server not available - skipping integration test")
    except Exception as e:
        pytest.fail(f"Error during list: {str(e)}")

def test_download_model():
    """Test downloading a model from the registry"""
    
    base_url = "http://localhost:3000"
    model_id = "sample-bert-model"
    version = "1.0.0"
    
    download_url = f"{base_url}/api/packages/models/{model_id}/versions/{version}/download"
    
    try:
        response = requests.get(download_url, timeout=30)

        assert response.status_code == 200, (
            f"Download failed with status {response.status_code}: "
            f"{response.text[:200]}"
        )

        # Validate content type
        content_type = response.headers.get("content-type", "")
        assert (
            "application/zip" in content_type or
            "application/octet-stream" in content_type
        ), f"Expected zip content type, got {content_type}"

        # Validate file content
        assert len(response.content) > 0, (
            "Downloaded file should not be empty"
        )

        # Save the downloaded file
        output_path = f"test_models/downloaded-{model_id}-{version}.zip"
        with open(output_path, 'wb') as f:
            f.write(response.content)

        # Validate file integrity - verify it's a valid ZIP
        assert os.path.exists(output_path), (
            f"Downloaded file should exist at {output_path}"
        )
        assert os.path.getsize(output_path) == len(response.content), (
            f"File size mismatch: expected {len(response.content)}, "
            f"got {os.path.getsize(output_path)}"
        )

        # Verify ZIP file is valid
        try:
            with zipfile.ZipFile(output_path, 'r') as zf:
                file_list = zf.namelist()
                assert len(file_list) > 0, (
                    "Downloaded ZIP file should contain files"
                )
                # Verify ZIP can be read
                zf.testzip()  # Returns None if ZIP is valid
        except zipfile.BadZipFile:
            pytest.fail(f"Downloaded file is not a valid ZIP: {output_path}")

    except requests.exceptions.ConnectionError:
        pytest.skip("Server not available - skipping integration test")
    except Exception as e:
        pytest.fail(f"Error during download: {str(e)}")

if __name__ == "__main__":
    print("Testing ACME Registry Package Operations")
    print("=" * 50)
    
    # Test upload
    try:
        test_upload_model()
        upload_success = True
    except (AssertionError, Exception) as e:
        print(f"Upload test failed: {e}")
        upload_success = False
    
    if upload_success:
        # Test list
        try:
            test_list_packages()
        except (AssertionError, Exception) as e:
            print(f"List test failed: {e}")
        
        # Test download
        try:
            test_download_model()
        except (AssertionError, Exception) as e:
            print(f"Download test failed: {e}")
    
    print("\n" + "=" * 50)
    print("Testing complete!")
