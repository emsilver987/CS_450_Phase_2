#!/usr/bin/env python3
"""
Populate Registry with 500 Real HuggingFace Models

This script populates the ACME Model Registry with 500 real models from HuggingFace,
including the required Tiny-LLM model for performance testing.
All models are stored in the performance/ path by default.

Usage:
    # Use S3 storage (direct S3 access, default):
    python scripts/populate_registry.py --s3
    
    # Use RDS storage via API (production):
    python scripts/populate_registry.py --rds
    
    # Use RDS storage via API (local server):
    python scripts/populate_registry.py --rds --local
    
    # Use RDS storage via API (custom URL):
    python scripts/populate_registry.py --rds --url http://localhost:8000
    
    # Or with environment variable:
    API_BASE_URL=http://localhost:3000 python scripts/populate_registry.py --rds
"""
import sys
import os
import time
import requests
import json
import argparse
import boto3
import uuid
import zipfile
import io
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path to import from src
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default URLs
DEFAULT_API_URL = "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod"
DEFAULT_LOCAL_URL = "http://localhost:8000"

HF_API_BASE = "https://huggingface.co/api"
MAX_RETRIES = 3
RETRY_DELAY = 2

# AWS Configuration (for performance mode)
REGION = os.getenv("AWS_REGION", "us-east-1")
ACCESS_POINT_NAME = os.getenv("S3_ACCESS_POINT_NAME", "cs450-s3")
ARTIFACTS_TABLE = os.getenv("DDB_TABLE_ARTIFACTS", "artifacts")

# Required model (must be included)
REQUIRED_MODEL = "arnir0/Tiny-LLM"

# Import the hardcoded list of 500 models
try:
    from scripts.huggingface_models_list import HF_MODELS_500
    POPULAR_MODELS = HF_MODELS_500
except ImportError:
    # Fallback if import fails - use minimal list
    POPULAR_MODELS = [
        "arnir0/Tiny-LLM",
        "bert-base-uncased",
        "distilbert-base-uncased",
        "roberta-base",
        "gpt2",
        "t5-small",
        "t5-base",
        "facebook/bart-base",
    ]


def get_authentication_token(api_base_url: str) -> Optional[str]:
    """Get authentication token for API requests"""
    try:
        response = requests.put(
            f"{api_base_url}/authenticate",
            json={
                "user": {
                    "name": "ece30861defaultadminuser",
                    "is_admin": True
                },
                "secret": {
                    "password": "correcthorsebatterystaple123(!__+@**(A'\"`;DROP TABLE artifacts;"
                }
            },
            timeout=10
        )
        if response.status_code == 200:
            token = response.text.strip('"')
            return token
        else:
            print(f"Warning: Authentication failed with status {response.status_code}")
            return None
    except Exception as e:
        print(f"Warning: Could not authenticate: {e}")
        return None


def get_hardcoded_models(count: int = None) -> List[str]:
    """
    Get hardcoded list of HuggingFace models.
    No API calls - just returns the pre-defined list.
    If count is None, returns all available models.
    """
    models = POPULAR_MODELS.copy()
    
    # Ensure REQUIRED_MODEL is first
    if REQUIRED_MODEL in models:
        models.remove(REQUIRED_MODEL)
        models.insert(0, REQUIRED_MODEL)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_models = []
    for model in models:
        if model not in seen:
            seen.add(model)
            unique_models.append(model)
    models = unique_models
    
    # Limit to count if specified
    if count is not None:
        models = models[:count]
    
    return models


# Removed check_model_exists - we'll skip existence checks and just ingest


def check_model_exists_on_hf(model_id: str) -> bool:
    """Check if a model exists on HuggingFace before attempting ingestion"""
    try:
        clean_model_id = model_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "")
        api_url = f"https://huggingface.co/api/models/{clean_model_id}"
        response = requests.get(api_url, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def get_s3_client_and_arn():
    """Get S3 client and access point ARN for S3 storage mode"""
    try:
        sts = boto3.client("sts", region_name=REGION)
        account_id = sts.get_caller_identity()["Account"]
        ap_arn = f"arn:aws:s3:{REGION}:{account_id}:accesspoint/{ACCESS_POINT_NAME}"
        s3 = boto3.client("s3", region_name=REGION)
        # Test connection
        s3.list_objects_v2(Bucket=ap_arn, Prefix="performance/", MaxKeys=1)
        return s3, ap_arn
    except Exception as e:
        print(f"Error initializing S3: {e}")
        print("Make sure AWS credentials are configured and S3 access point exists")
        return None, None


def get_dynamodb_table():
    """Get DynamoDB artifacts table for S3 storage mode"""
    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(ARTIFACTS_TABLE)
        # Test access
        table.scan(Limit=1)
        return table
    except Exception as e:
        print(f"Error accessing DynamoDB: {e}")
        return None


def download_from_huggingface(model_id: str, version: str = "main", download_all: bool = False) -> bytes:
    """Download model files from HuggingFace and create ZIP
    
    Args:
        model_id: HuggingFace model identifier
        version: Model version/branch (default: "main")
        download_all: If True, download all files including model weights. If False, only essential/config files.
                      WARNING: download_all=True can be very slow for large models (several GB).
    """
    try:
        clean_model_id = model_id.replace("https://huggingface.co/", "").replace("http://huggingface.co/", "")
        api_url = f"https://huggingface.co/api/models/{clean_model_id}"
        
        response = requests.get(api_url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Model {clean_model_id} not found on HuggingFace")
        
        model_info = response.json()
        all_files = []
        for sibling in model_info.get("siblings", []):
            if sibling.get("rfilename"):
                all_files.append(sibling["rfilename"])
        
        if download_all:
            # Smart download: essential files + ONE main weight file + tokenizer files
            # This matches what the original API does but includes the actual model binary
            
            # 1. Essential files (config, README, etc.)
            essential_files = []
            for filename in all_files:
                if filename.endswith((".json", ".md", ".txt", ".yml", ".yaml")):
                    essential_files.append(filename)
                elif filename.startswith("README") or filename.startswith("readme"):
                    essential_files.append(filename)
                elif filename in ["config.json", "LICENSE", "license", "LICENCE", "licence"]:
                    essential_files.append(filename)
            
            # 2. Find ONE main weight file (prefer .safetensors, then pytorch_model.bin, skip CoreML/others)
            weight_files = [f for f in all_files if any(f.endswith(ext) for ext in [".safetensors", ".bin", ".pt", ".pth"]) 
                          and not any(exclude in f.lower() for exclude in ["coreml", "onnx", "tf", "tflite", "mlpackage"])]
            main_weight_file = None
            if weight_files:
                # Prefer model.safetensors or pytorch_model.bin in root
                for preferred in ["model.safetensors", "pytorch_model.bin"]:
                    if preferred in weight_files:
                        main_weight_file = preferred
                        break
                # If no preferred found, take the first one (smallest path usually)
                if not main_weight_file:
                    # Prefer files in root directory (shorter paths)
                    root_files = [f for f in weight_files if "/" not in f]
                    main_weight_file = root_files[0] if root_files else weight_files[0]
            
            # 3. Tokenizer files (needed for model to work)
            tokenizer_files = [f for f in all_files if "tokenizer" in f.lower() and 
                              (f.endswith(".json") or f.endswith(".model") or "vocab" in f.lower())]
            
            # Combine: essential + one weight file + tokenizer files
            files_to_download = essential_files.copy()
            if main_weight_file:
                files_to_download.append(main_weight_file)
            files_to_download.extend(tokenizer_files)
            
            # Remove duplicates
            files_to_download = list(dict.fromkeys(files_to_download))  # Preserves order
            
            print(f"    Downloading {len(files_to_download)} files", end="")
            if main_weight_file:
                print(f" (1 weight file: {main_weight_file.split('/')[-1]})", end="")
            if tokenizer_files:
                print(f", {len(tokenizer_files)} tokenizer file(s)", end="")
            print("...")
        else:
            # Get essential files only (same logic as s3_service.py)
            essential_files = []
            for filename in all_files:
                if filename.endswith((".json", ".md", ".txt", ".yml", ".yaml")):
                    essential_files.append(filename)
                elif filename.startswith("README") or filename.startswith("readme"):
                    essential_files.append(filename)
                elif filename in ["config.json", "LICENSE", "license", "LICENCE", "licence"]:
                    essential_files.append(filename)
            files_to_download = essential_files
        
        if not files_to_download:
            raise Exception(f"No files found for model {clean_model_id}")
        
        if not download_all:
            print(f"    Downloading {len(files_to_download)} essential file(s)...")
        
        # Download files and create ZIP
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zip_file:
            def download_file(url: str, filename: str) -> tuple:
                try:
                    is_large_file = any(filename.endswith(ext) for ext in [".bin", ".safetensors", ".pt", ".pth", ".ckpt"])
                    if is_large_file:
                        print(f"      Downloading {filename} (model weights, may take a moment)...")
                    else:
                        print(f"      Downloading {filename}...")
                    
                    # Use streaming for large files, regular for small ones
                    if is_large_file:
                        file_response = requests.get(url, timeout=600, stream=True)
                    else:
                        file_response = requests.get(url, timeout=120)
                    
                    if file_response.status_code == 200:
                        if is_large_file and hasattr(file_response, 'iter_content'):
                            # Stream large files to avoid memory issues
                            content = b""
                            for chunk in file_response.iter_content(chunk_size=8192):
                                if chunk:
                                    content += chunk
                        else:
                            content = file_response.content
                        
                        size_mb = len(content) / (1024 * 1024)
                        if size_mb > 1:
                            print(f"      ✓ Downloaded {filename} ({size_mb:.2f} MB)")
                        else:
                            size_kb = len(content) / 1024
                            print(f"      ✓ Downloaded {filename} ({size_kb:.1f} KB)")
                        return (filename, content)
                    else:
                        print(f"      ✗ Failed to download {filename}: HTTP {file_response.status_code}")
                        return (filename, None)
                except requests.exceptions.Timeout:
                    print(f"      ✗ Timeout downloading {filename} (file may be too large)")
                    return (filename, None)
                except Exception as e:
                    print(f"      ✗ Error downloading {filename}: {str(e)}")
                    return (filename, None)
            
            urls = [
                (f"https://huggingface.co/{clean_model_id}/resolve/{version}/{filename}", filename)
                for filename in files_to_download
            ]
            
            # Download sequentially to avoid overwhelming memory and network
            # This also gives better progress visibility
            downloaded_count = 0
            failed_count = 0
            total_size = 0
            
            for i, (url, filename) in enumerate(urls, 1):
                filename_result, content = download_file(url, filename)
                if content:
                    zip_file.writestr(filename_result, content)
                    downloaded_count += 1
                    total_size += len(content)
                else:
                    failed_count += 1
                    # Don't fail completely if a non-critical file fails
                    if filename in ["config.json"]:
                        raise Exception(f"Failed to download critical file: {filename}")
            
            if downloaded_count == 0:
                raise Exception(f"Failed to download any files for model {clean_model_id}")
            
            if failed_count > 0:
                print(f"    ⚠ {failed_count} file(s) failed to download (continuing with {downloaded_count} successful)")
            
            total_mb = total_size / (1024 * 1024)
            print(f"    Total downloaded: {total_mb:.2f} MB ({downloaded_count} files)")
        
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Failed to download from HuggingFace: {str(e)}")


def get_performance_s3_key(model_id: str, version: str = "main") -> str:
    """Get the S3 key for a model in performance/ path (without uploading)"""
    safe_model_id = (
        model_id.replace("https://huggingface.co/", "")
        .replace("http://huggingface.co/", "")
        .replace("/", "_")
        .replace(":", "_")
        .replace("\\", "_")
        .replace("?", "_")
        .replace("*", "_")
        .replace('"', "_")
        .replace("<", "_")
        .replace(">", "_")
        .replace("|", "_")
    )
    safe_version = version.replace("/", "_").replace(":", "_").replace("\\", "_")
    return f"performance/{safe_model_id}/{safe_version}/model.zip"


def check_model_exists_in_s3(s3, ap_arn: str, model_id: str, version: str = "main") -> bool:
    """Check if a model already exists in S3 at performance/ path"""
    try:
        s3_key = get_performance_s3_key(model_id, version)
        s3.head_object(Bucket=ap_arn, Key=s3_key)
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "404" or error_code == "NoSuchKey":
            return False
        # For other errors, assume it doesn't exist and let the upload handle it
        return False
    except Exception:
        return False


def upload_model_to_performance_s3(s3, ap_arn: str, model_id: str, version: str, zip_content: bytes) -> str:
    """Upload model ZIP directly to S3 at performance/ path"""
    s3_key = get_performance_s3_key(model_id, version)
    
    s3.put_object(
        Bucket=ap_arn,
        Key=s3_key,
        Body=zip_content,
        ContentType="application/zip"
    )
    
    return s3_key


def create_dummy_model_metadata(table, model_id: str, version: str = "main") -> bool:
    """Create a dummy model entry in DynamoDB (metadata-only, no actual file)"""
    try:
        artifact_id = str(uuid.uuid4())
        safe_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
        )
        
        item = {
            "artifact_id": artifact_id,
            "name": model_id,  # Original name
            "type": "model",
            "version": version,
            "url": f"https://huggingface.co/{model_id}",
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        
        table.put_item(Item=item)
        return True
    except Exception as e:
        print(f"  Error creating metadata for {model_id}: {str(e)}")
        return False


def ingest_model_performance_mode(s3, ap_arn: str, table, model_id: str, version: str = "main", skip_missing: bool = True, skip_existing: bool = True) -> tuple:
    """
    Ingest model in S3 mode: download from HF and upload to S3 at performance/ path.
    - Tiny-LLM: Downloads full model including binary (needed for performance testing)
    - Other models: Downloads only essential files (config, README, etc.) for speed
    
    Args:
        skip_existing: If True, skip models that already exist in S3 (avoids re-uploading)
    
    Returns:
        (success: bool, status: Optional[str]) where status can be:
        - None: success
        - "already_exists": model already exists in S3 (skipped)
        - "not_found": model doesn't exist on HuggingFace (404)
        - "error": other error occurred
    """
    # Check if model already exists in S3 (skip to avoid re-uploading)
    if skip_existing:
        if check_model_exists_in_s3(s3, ap_arn, model_id, version):
            print(f"  ⊘ Model already exists in S3: {model_id} (skipping)")
            return (True, "already_exists")  # Count as success since it's already there
    
    # Check if model exists on HuggingFace first
    if skip_missing:
        if not check_model_exists_on_hf(model_id):
            print(f"  ⊘ Model not found on HuggingFace: {model_id} (skipping)")
            return (False, "not_found")
    
    # Full ingestion: download and upload to S3
    try:
        # Tiny-LLM needs the full model (including binary) for performance testing
        # Other models only need essential files for registry population
        is_tiny_llm = (model_id == REQUIRED_MODEL)
        
        if is_tiny_llm:
            print(f"  Downloading full model from HuggingFace (including model weights for performance testing)...")
            # Download essential files + ONE main weight file + tokenizer files
            zip_content = download_from_huggingface(model_id, version, download_all=True)
        else:
            print(f"  Downloading essential files from HuggingFace (config, README, etc.)...")
            # Download only essential files (no model weights - faster!)
            zip_content = download_from_huggingface(model_id, version, download_all=False)
        
        zip_size_mb = len(zip_content) / (1024 * 1024)
        print(f"  ✓ Downloaded {len(zip_content):,} bytes ({zip_size_mb:.2f} MB) total")
        
        print(f"  Uploading to S3 at performance/ path...")
        s3_key = upload_model_to_performance_s3(s3, ap_arn, model_id, version, zip_content)
        print(f"  ✓ Uploaded to: {s3_key}")
        
        # Create metadata in DynamoDB
        artifact_id = str(uuid.uuid4())
        safe_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
        )
        
        item = {
            "artifact_id": artifact_id,
            "name": model_id,
            "type": "model",
            "version": version,
            "url": f"https://huggingface.co/{model_id}",
            "s3_path": s3_key,  # Store the performance/ path
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        
        table.put_item(Item=item)
        print(f"  ✓ Metadata created in DynamoDB")
        
        return (True, None)
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "404" in error_msg:
            print(f"  ⊘ Model not found: {model_id} (skipping)")
            return (False, "not_found")
        else:
            print(f"  ✗ Failed: {error_msg}")
            return (False, "error")


def ingest_model(api_base_url: str, model_id: str, auth_token: Optional[str], retry: int = 0, skip_missing: bool = True) -> tuple:
    """
    Ingest a single model into the registry.
    
    Returns:
        (success: bool, status: Optional[str]) where status can be:
        - None: success
        - "not_found": model doesn't exist on HuggingFace (404)
        - "error": other error occurred
    """
    # Quick check if model exists on HuggingFace (avoid unnecessary API calls)
    if skip_missing:
        if not check_model_exists_on_hf(model_id):
            print(f"⊘ Model not found on HuggingFace: {model_id} (skipping)")
            return (False, "not_found")
    
    try:
        headers = {"Content-Type": "application/json"}
        if auth_token:
            headers["X-Authorization"] = auth_token
        
        # Use the /artifact/model endpoint to ingest
        url = f"{api_base_url}/artifact/model"
        payload = {
            "url": f"https://huggingface.co/{model_id}"
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=300)
        
        if response.status_code in [200, 201, 202]:
            print(f"✓ Successfully ingested: {model_id}")
            return (True, None)
        elif response.status_code == 409:
            print(f"⊘ Already exists: {model_id} (skipping)")
            return (True, None)  # Consider existing models as success
        elif response.status_code == 404:
            # Model doesn't exist - don't retry
            error_text = response.text[:200]
            if "not found on HuggingFace" in error_text or "not found" in error_text.lower():
                print(f"⊘ Model not found: {model_id} (skipping)")
                return (False, "not_found")
            else:
                print(f"✗ Failed to ingest {model_id}: HTTP {response.status_code} - {error_text}")
                return (False, "error")
        else:
            print(f"✗ Failed to ingest {model_id}: HTTP {response.status_code} - {response.text[:200]}")
            if retry < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY}s... (attempt {retry + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                return ingest_model(api_base_url, model_id, auth_token, retry + 1, skip_missing=False)
            return (False, "error")
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout ingesting {model_id}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model(api_base_url, model_id, auth_token, retry + 1, skip_missing=False)
        return (False, "error")
    except Exception as e:
        print(f"✗ Error ingesting {model_id}: {str(e)}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model(api_base_url, model_id, auth_token, retry + 1, skip_missing=False)
        return (False, "error")


def parse_arguments():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(
        description="Populate ACME Model Registry with 500 HuggingFace models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/populate_registry.py --s3              # Use S3 storage (direct access, default)
  python scripts/populate_registry.py --rds --local     # Use RDS storage via API (local server)
  python scripts/populate_registry.py --rds --url http://localhost:8000  # Use RDS storage via API (custom URL)
  python scripts/populate_registry.py --s3 --local     # Use S3 storage (direct access, local server for metadata)
        """
    )
    
    # Storage backend flags (mutually exclusive)
    storage_group = parser.add_mutually_exclusive_group()
    storage_group.add_argument(
        "--s3",
        action="store_true",
        help="Use S3 storage backend (direct S3 access, default)"
    )
    storage_group.add_argument(
        "--rds",
        action="store_true",
        help="Use RDS storage backend (via API endpoints)"
    )
    
    # --local and --url are mutually exclusive
    url_group = parser.add_mutually_exclusive_group()
    url_group.add_argument(
        "--local",
        action="store_true",
        help=f"Use local server at {DEFAULT_LOCAL_URL} (for RDS mode or metadata)"
    )
    url_group.add_argument(
        "--url",
        type=str,
        metavar="URL",
        help="Custom API base URL (e.g., http://localhost:8000). Used for RDS mode."
    )
    
    return parser.parse_args()


def get_api_base_url(args: argparse.Namespace) -> str:
    """Determine the API base URL from arguments or environment"""
    # Priority: CLI args > environment variable > default
    if args.url:
        return args.url.rstrip("/")
    elif args.local:
        return DEFAULT_LOCAL_URL
    elif os.getenv("API_BASE_URL"):
        return os.getenv("API_BASE_URL").rstrip("/")
    else:
        return DEFAULT_API_URL


def ingest_model_rds_direct(model_id: str, zip_content: bytes, version: str = "main", skip_missing: bool = True, skip_existing: bool = True) -> tuple:
    """
    Ingest a single model into RDS via direct database connection.
    Used for large files (>10MB) that exceed API Gateway payload limit.
    
    Returns:
        (success: bool, status: Optional[str]) where status can be:
        - None: success
        - "already_exists": model already exists in RDS (skipped)
        - "not_found": model doesn't exist on HuggingFace (404)
        - "error": other error occurred
        - "no_credentials": RDS credentials not available
    """
    # Check if RDS credentials are available
    import os
    rds_endpoint = os.getenv("RDS_ENDPOINT", "")
    rds_password = os.getenv("RDS_PASSWORD", "")
    
    if not rds_endpoint or not rds_password:
        error_msg = "RDS credentials not available locally. Cannot use direct RDS access for large files."
        print(f"✗ {error_msg}")
        print(f"  Set RDS_ENDPOINT and RDS_PASSWORD environment variables to enable direct RDS access.")
        return (False, "no_credentials")
    
    # Quick check if model exists on HuggingFace (avoid unnecessary work)
    if skip_missing:
        if not check_model_exists_on_hf(model_id):
            print(f"⊘ Model not found on HuggingFace: {model_id} (skipping)")
            return (False, "not_found")
    
    try:
        # Import RDS service components directly
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.services.rds_service import get_connection_pool, model_exists as rds_model_exists
        import psycopg2
        from fastapi import HTTPException
        
        # Sanitize model_id for RDS (same as API)
        sanitized_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
            .replace(":", "_")
            .replace("\\", "_")
            .replace("?", "_")
            .replace("*", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
        )
        
        # Check if model already exists in RDS
        if skip_existing:
            try:
                if rds_model_exists(sanitized_model_id, version, "full", use_performance_path=True):
                    print(f"  ⊘ Model already exists in RDS: {model_id} (skipping)")
                    return (True, "already_exists")
            except HTTPException as e:
                # If RDS service raises HTTPException, convert to regular exception
                if "503" in str(e.status_code) or "configuration missing" in str(e.detail).lower():
                    raise Exception(f"RDS configuration error: {e.detail}")
                raise
        
        # Upload directly to RDS using performance path
        path_prefix = "performance"
        component = "full"
        
        pool = get_connection_pool()
        conn = pool.getconn()
        cursor = conn.cursor()
        
        try:
            # Insert or update model file
            cursor.execute("""
                INSERT INTO model_files (model_id, version, component, path_prefix, file_data, file_size)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (model_id, version, component, path_prefix)
                DO UPDATE SET
                    file_data = EXCLUDED.file_data,
                    file_size = EXCLUDED.file_size,
                    created_at = CURRENT_TIMESTAMP
            """, (sanitized_model_id, version, component, path_prefix, psycopg2.Binary(zip_content), len(zip_content)))
            
            conn.commit()
            print(f"✓ Successfully ingested to RDS: {model_id} ({len(zip_content) / (1024*1024):.2f} MB)")
            return (True, None)
        except Exception as db_error:
            conn.rollback()
            raise db_error
        finally:
            pool.putconn(conn)
        
    except HTTPException as e:
        # Convert FastAPI HTTPException to regular exception for script context
        error_msg = f"{e.status_code}: {e.detail}"
        if "not found" in error_msg.lower() or "404" in error_msg:
            print(f"⊘ Model not found: {model_id} (skipping)")
            return (False, "not_found")
        else:
            print(f"✗ Failed: {error_msg}")
            return (False, "error")
    except Exception as e:
        error_msg = str(e)
        if "not found" in error_msg.lower() or "404" in error_msg:
            print(f"⊘ Model not found: {model_id} (skipping)")
            return (False, "not_found")
        else:
            print(f"✗ Failed: {error_msg}")
            return (False, "error")


def ingest_model_rds_via_api(api_base_url: str, model_id: str, auth_token: Optional[str], zip_content: bytes, version: str = "main", retry: int = 0, skip_missing: bool = True) -> tuple:
    """
    Ingest a single model into RDS via API endpoint.
    For files >10MB, falls back to direct RDS access to bypass API Gateway limit.
    
    Returns:
        (success: bool, status: Optional[str]) where status can be:
        - None: success
        - "not_found": model doesn't exist on HuggingFace (404)
        - "error": other error occurred
    """
    # API Gateway has a 10MB payload limit
    # For files larger than 10MB, try direct RDS access if credentials are available
    MAX_API_PAYLOAD_SIZE = 10 * 1024 * 1024  # 10MB
    
    if len(zip_content) > MAX_API_PAYLOAD_SIZE:
        print(f"  ⚠ File size ({len(zip_content) / (1024*1024):.2f} MB) exceeds API Gateway 10MB limit")
        # Try direct RDS access first (if credentials available)
        result = ingest_model_rds_direct(model_id, zip_content, version, skip_missing=skip_missing)
        if result[0] or result[1] != "no_credentials":
            # Success or error other than missing credentials
            return result
        # If credentials not available, still try API (will fail with 413, but we handle it)
        print(f"  Falling back to API endpoint (will fail with 413, but attempting anyway)...")
    
    # Quick check if model exists on HuggingFace (avoid unnecessary API calls)
    if skip_missing:
        if not check_model_exists_on_hf(model_id):
            print(f"⊘ Model not found on HuggingFace: {model_id} (skipping)")
            return (False, "not_found")
    
    try:
        headers = {}
        if auth_token:
            headers["X-Authorization"] = auth_token
        
        # Sanitize model_id for URL (same as S3)
        sanitized_model_id = (
            model_id.replace("https://huggingface.co/", "")
            .replace("http://huggingface.co/", "")
            .replace("/", "_")
            .replace(":", "_")
            .replace("\\", "_")
            .replace("?", "_")
            .replace("*", "_")
            .replace('"', "_")
            .replace("<", "_")
            .replace(">", "_")
            .replace("|", "_")
        )
        
        # Use the RDS upload endpoint
        url = f"{api_base_url}/artifact/model/{sanitized_model_id}/upload-rds?version={version}&path_prefix=performance"
        
        # Prepare multipart form data
        files = {
            'file': (f"{sanitized_model_id}_{version}.zip", zip_content, 'application/zip')
        }
        
        response = requests.post(url, files=files, headers=headers, timeout=300)
        
        if response.status_code in [200, 201, 202]:
            print(f"✓ Successfully ingested to RDS: {model_id}")
            return (True, None)
        elif response.status_code == 409:
            print(f"⊘ Already exists in RDS: {model_id} (skipping)")
            return (True, None)  # Consider existing models as success
        elif response.status_code == 413:
            # Payload too large - try direct RDS access
            print(f"  ⚠ HTTP 413: Payload too large for API Gateway (file size: {len(zip_content) / (1024*1024):.2f} MB)")
            print(f"  Attempting direct RDS access...")
            result = ingest_model_rds_direct(model_id, zip_content, version, skip_missing=False)
            if result[1] == "no_credentials":
                print(f"  ✗ Cannot upload large file: RDS credentials not available locally.")
                print(f"  To upload files >10MB, set RDS_ENDPOINT and RDS_PASSWORD environment variables.")
                return (False, "error")
            return result
        elif response.status_code == 404:
            error_text = response.text[:200]
            if "not found on HuggingFace" in error_text or "not found" in error_text.lower():
                print(f"⊘ Model not found: {model_id} (skipping)")
                return (False, "not_found")
            else:
                print(f"✗ Failed to ingest {model_id}: HTTP {response.status_code} - {error_text}")
                return (False, "error")
        else:
            print(f"✗ Failed to ingest {model_id}: HTTP {response.status_code} - {response.text[:200]}")
            if retry < MAX_RETRIES:
                print(f"  Retrying in {RETRY_DELAY}s... (attempt {retry + 1}/{MAX_RETRIES})")
                time.sleep(RETRY_DELAY)
                return ingest_model_rds_via_api(api_base_url, model_id, auth_token, zip_content, version, retry + 1, skip_missing=False)
            return (False, "error")
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout ingesting {model_id}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model_rds_via_api(api_base_url, model_id, auth_token, zip_content, version, retry + 1, skip_missing=False)
        return (False, "error")
    except Exception as e:
        error_str = str(e)
        # Check if it's a payload size error
        if "413" in error_str or "content length exceeded" in error_str.lower():
            print(f"  ⚠ Payload too large for API Gateway (file size: {len(zip_content) / (1024*1024):.2f} MB)")
            print(f"  Attempting direct RDS access...")
            result = ingest_model_rds_direct(model_id, zip_content, version, skip_missing=False)
            if result[1] == "no_credentials":
                print(f"  ✗ Cannot upload large file: RDS credentials not available locally.")
                print(f"  To upload files >10MB, set RDS_ENDPOINT and RDS_PASSWORD environment variables.")
                return (False, "error")
            return result
        print(f"✗ Error ingesting {model_id}: {error_str}")
        if retry < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return ingest_model_rds_via_api(api_base_url, model_id, auth_token, zip_content, version, retry + 1, skip_missing=False)
        return (False, "error")


def main():
    """Main function to populate registry with 500 models"""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Determine storage backend (default to S3)
    use_rds = args.rds
    use_s3 = args.s3 or (not args.rds)  # Default to S3 if neither specified
    
    # S3 mode: direct S3/DynamoDB writes (bypasses API)
    if use_s3:
        return main_performance_mode()
    
    # RDS mode: use API endpoints
    api_base_url = get_api_base_url(args)
    
    print("=" * 80)
    print("ACME Model Registry Population Script")
    print("RDS MODE (stores in performance/ RDS path via API)")
    print("=" * 80)
    print(f"API Base URL: {api_base_url}")
    if args.local:
        print("Mode: Local")
    elif args.url:
        print(f"Mode: Custom URL")
    elif os.getenv("API_BASE_URL"):
        print("Mode: Environment Variable")
    else:
        print("Mode: Remote API (default)")
    print()
    
    # Get authentication token
    print("Authenticating...")
    auth_token = get_authentication_token(api_base_url)
    if auth_token:
        print("✓ Authentication successful")
    else:
        print("✗ Authentication failed - cannot proceed without admin token")
        return 1
    print()
    
    # Get hardcoded list of 500 models
    print("Loading hardcoded list of 500 HuggingFace models...")
    models = get_hardcoded_models(count=500)
    print(f"✓ Loaded {len(models)} models to ingest")
    
    # Ensure REQUIRED_MODEL is first
    if REQUIRED_MODEL in models:
        models.remove(REQUIRED_MODEL)
    models.insert(0, REQUIRED_MODEL)
    models = models[:500]  # Ensure exactly 500
    
    print(f"Will ingest {len(models)} models (starting with {REQUIRED_MODEL})")
    print(f"  - Tiny-LLM: Full model download (including binary - needed for performance testing)")
    print(f"  - Other models: Essential files only (config, README, etc. - for speed)")
    print(f"  - All files will be uploaded to performance/ RDS path via API")
    print()
    
    # Start ingesting models
    print("Starting model ingestion (will continue until 500 successful submissions)...")
    print("=" * 80)
    
    successful = 0
    failed = 0
    not_found = 0
    not_found_models = []
    tiny_llm_ingested = False
    target_successful = 500
    models_processed = 0
    
    for model_id in models:
        # Stop if we've reached the target
        if successful >= target_successful:
            print()
            print(f"✓ Reached target of {target_successful} successful submissions!")
            break
        
        models_processed += 1
        print(f"[{models_processed}] Ingesting: {model_id} (Success: {successful}/{target_successful})")
        
        # Download from HuggingFace first
        try:
            is_tiny_llm = (model_id == REQUIRED_MODEL)
            if is_tiny_llm:
                print(f"  Downloading full model from HuggingFace (including model weights for performance testing)...")
                zip_content = download_from_huggingface(model_id, "main", download_all=True)
            else:
                print(f"  Downloading essential files from HuggingFace (config, README, etc.)...")
                zip_content = download_from_huggingface(model_id, "main", download_all=False)
            
            zip_size_mb = len(zip_content) / (1024 * 1024)
            print(f"  ✓ Downloaded {len(zip_content):,} bytes ({zip_size_mb:.2f} MB) total")
            
            # Upload to RDS via API
            result, status = ingest_model_rds_via_api(api_base_url, model_id, auth_token, zip_content, "main", skip_missing=True)
            if result:
                successful += 1
                if model_id == REQUIRED_MODEL:
                    tiny_llm_ingested = True
                print(f"✓ Successfully ingested {model_id} to RDS performance/ path ({successful}/{target_successful})")
            elif status == "not_found":
                not_found += 1
                not_found_models.append(model_id)
                print(f"  ⊘ Model not found on HuggingFace: {model_id} (skipping)")
            else:
                failed += 1
                print(f"  ✗ Failed to ingest {model_id}")
        except Exception as e:
            failed += 1
            print(f"  ✗ Error processing {model_id}: {str(e)}")
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
        
        # Progress update every 50 models
        if models_processed % 50 == 0:
            print()
            print(f"Progress: {models_processed} processed, {successful} successful/{target_successful} target ({failed} failed, {not_found} not found)")
            print()
    
    # Final summary
    print()
    print("=" * 80)
    print("Ingestion Summary")
    print("=" * 80)
    print(f"Total models processed: {models_processed}")
    print(f"  - Successfully ingested to RDS performance/ path: {successful}")
    print(f"  - Tiny-LLM ingested: {'✓' if tiny_llm_ingested else '✗'}")
    print(f"  - Not found on HuggingFace: {not_found}")
    print(f"  - Failed (other errors): {failed}")
    print(f"Target: {target_successful} successful submissions")
    print()
    
    if not_found_models:
        print(f"⚠ {len(not_found_models)} models not found on HuggingFace:")
        for model in not_found_models[:10]:
            print(f"     - {model}")
        if len(not_found_models) > 10:
            print(f"     ... and {len(not_found_models) - 10} more")
        print()
    
    if successful >= target_successful:
        print(f"✓ Registry populated with {successful} models for performance testing")
        print("  Note: Models stored in performance/ RDS path (via API)")
        return 0
    else:
        print(f"⚠ Only {successful} models successfully ingested (target: {target_successful})")
        print(f"⚠ Processed {models_processed} models but ran out of models in the list")
        print(f"⚠ Consider adding more models to the hardcoded list")
        return 1


def main_performance_mode():
    """Main function for S3 mode: direct S3/DynamoDB writes"""
    print("=" * 80)
    print("ACME Model Registry Population Script")
    print("S3 MODE (stores in performance/ S3 path)")
    print("=" * 80)
    print()
    
    # Initialize AWS clients
    print("Initializing AWS clients...")
    s3, ap_arn = get_s3_client_and_arn()
    if not s3 or not ap_arn:
        print("✗ Failed to initialize S3 client")
        return 1
    
    table = get_dynamodb_table()
    if not table:
        print("✗ Failed to access DynamoDB table")
        return 1
    
    print(f"✓ S3 Access Point: {ap_arn}")
    print(f"✓ DynamoDB Table: {ARTIFACTS_TABLE}")
    print()
    
    # Get all available models (no limit - we'll continue until 500 successful)
    all_models = get_hardcoded_models(count=None)
    
    # Ensure REQUIRED_MODEL is first
    if REQUIRED_MODEL in all_models:
        all_models.remove(REQUIRED_MODEL)
    all_models.insert(0, REQUIRED_MODEL)
    
    print(f"Loaded {len(all_models)} models from hardcoded list")
    print(f"  - Tiny-LLM: Full model download (including binary - needed for performance testing)")
    print(f"  - Other models: Essential files only (config, README, etc. - for speed)")
    print(f"  - All files will be uploaded to performance/ S3 path")
    print(f"  - Will continue until 500 successful submissions")
    print()
    
    # Start processing
    print("Starting model ingestion (will continue until 500 successful submissions)...")
    print("=" * 80)
    
    successful = 0
    failed = 0
    not_found = 0
    not_found_models = []
    tiny_llm_ingested = False
    target_successful = 500
    models_processed = 0
    
    for model_id in all_models:
        # Stop if we've reached the target
        if successful >= target_successful:
            print()
            print(f"✓ Reached target of {target_successful} successful submissions!")
            break
        
        models_processed += 1
        print(f"[{models_processed}] Ingesting: {model_id} (Success: {successful}/{target_successful})")
        
        result, status = ingest_model_performance_mode(s3, ap_arn, table, model_id, "main", skip_missing=True, skip_existing=True)
        if result:
            successful += 1
            if model_id == REQUIRED_MODEL:
                tiny_llm_ingested = True
            if status == "already_exists":
                print(f"⊘ Already exists (skipped): {model_id} ({successful}/{target_successful})")
            else:
                print(f"✓ Successfully ingested {model_id} to performance/ S3 path ({successful}/{target_successful})")
        elif status == "not_found":
            not_found += 1
            not_found_models.append(model_id)
            print(f"  ⊘ Model not found on HuggingFace: {model_id} (skipping)")
        else:
            failed += 1
            print(f"  ✗ Failed to ingest {model_id}")
        
        # Small delay to avoid rate limiting
        time.sleep(0.5)
        
        # Progress update every 50 models
        if models_processed % 50 == 0:
            print()
            print(f"Progress: {models_processed} processed, {successful} successful/{target_successful} target ({failed} failed, {not_found} not found)")
            print()
    
    # Final summary
    print()
    print("=" * 80)
    print("Ingestion Summary")
    print("=" * 80)
    print(f"Total models processed: {models_processed}")
    print(f"  - Successfully ingested to performance/ S3 path: {successful}")
    print(f"  - Tiny-LLM ingested: {'✓' if tiny_llm_ingested else '✗'}")
    print(f"  - Not found on HuggingFace: {not_found}")
    print(f"  - Failed (other errors): {failed}")
    print(f"Target: {target_successful} successful submissions")
    print()
    
    if not_found_models:
        print(f"⚠ {len(not_found_models)} models not found on HuggingFace:")
        for model in not_found_models[:10]:
            print(f"     - {model}")
        if len(not_found_models) > 10:
            print(f"     ... and {len(not_found_models) - 10} more")
        print()
    
    if successful >= target_successful:
        print(f"✓ Registry populated with {successful} models for performance testing")
        print("  Note: Models stored in performance/ S3 path (not models/)")
        return 0
    else:
        print(f"⚠ Only {successful} models successfully ingested (target: {target_successful})")
        print(f"⚠ Processed {models_processed} models but ran out of models in the list")
        print(f"⚠ Consider adding more models to the hardcoded list")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
