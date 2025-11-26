#!/usr/bin/env python3
"""
Test script for uploading models to the ACME Registry
"""
import requests
import json
import os
import pytest

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
        # Read the ZIP file
        with open(zip_path, 'rb') as f:
            files = {'file': ('sample-model.zip', f, 'application/zip')}
            
            print(f"Uploading model {model_id} version {version}...")
            response = requests.post(upload_url, files=files, timeout=30)
            
            assert response.status_code == 200, f"Upload failed with status {response.status_code}: {response.text}"
            
            result = response.json()
            print(f"[SUCCESS] Upload successful!")
            print(f"Response: {json.dumps(result, indent=2)}")
                
    except requests.exceptions.ConnectionError:
        pytest.skip("Server not available - skipping integration test")
    except Exception as e:
        pytest.fail(f"Error during upload: {str(e)}")

def test_list_packages():
    """Test listing packages in the registry"""
    
    base_url = "http://localhost:3000"
    list_url = f"{base_url}/api/packages"
    
    try:
        print("\n[INFO] Listing packages...")
        response = requests.get(list_url, timeout=5)
        
        assert response.status_code == 200, f"List failed with status {response.status_code}: {response.text}"
        
        result = response.json()
        print(f"[SUCCESS] List successful!")
        print(f"Response: {json.dumps(result, indent=2)}")
            
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
        print(f"\n[INFO] Downloading model {model_id} version {version}...")
        response = requests.get(download_url, timeout=30)
        
        assert response.status_code == 200, f"Download failed with status {response.status_code}: {response.text}"
        
        # Save the downloaded file
        output_path = f"test_models/downloaded-{model_id}-{version}.zip"
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f"[SUCCESS] Download successful!")
        print(f"Downloaded file saved to: {output_path}")
        print(f"File size: {len(response.content)} bytes")
            
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
