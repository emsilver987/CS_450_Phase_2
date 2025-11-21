from __future__ import annotations
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import io
import re
from botocore.exceptions import ClientError
from ..services.s3_service import (
    upload_model,
    download_model,
    list_models,
    reset_registry,
    sync_model_lineage_to_neptune,
    get_model_lineage_from_config,
    get_model_sizes,
    model_ingestion,
)
from ..services.validator_service import log_upload_event
from ..services.auth_service import verify_jwt_token

router = APIRouter()


def _get_user_id_from_request(request: Request) -> str:
    """
    Extract user_id from JWT token in request headers for audit logging.
    Returns 'unknown' if token cannot be decoded.
    """
    raw = (
        request.headers.get("x-authorization")
        or request.headers.get("authorization")
        or ""
    )
    raw = raw.strip()

    if not raw:
        return "unknown"

    # Normalize: allow "Bearer <token>" or legacy "bearer <token>"
    if raw.lower().startswith("bearer "):
        token = raw.split(" ", 1)[1].strip()
    else:
        token = raw.strip()

    if not token:
        return "unknown"

    # Check if this is the static token (autograder compatibility)
    # We don't import STATIC_TOKEN to avoid circular imports, just check string
    if token == "1982jhk12h3123":  # Hardcoded fallback or check if we can import
        return "autograder"

    # Try to decode JWT to extract user_id
    try:
        decoded_token = verify_jwt_token(token)
        if decoded_token:
            return decoded_token.get('user_id', decoded_token.get('username', 'unknown'))
    except Exception:
        pass
    
    return "unknown"


@router.get("/rate/{name}")
def rate_package(name: str):
    try:
        from ..services.rating import run_scorer

        result = run_scorer(name)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rate package: {str(e)}")


@router.get("/search")
def search_packages(q: str = Query(..., description="Search query for model names")):
    try:
        import re

        escaped_query = re.escape(q)
        name_regex = f".*{escaped_query}.*"
        result = list_models(name_regex=name_regex, limit=100)
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search packages: {str(e)}"
        )


@router.get("/search/model-cards")
def search_model_cards(
    q: str = Query(..., description="Search query for model card content")
):
    try:
        import re

        escaped_query = re.escape(q)
        model_regex = f".*{escaped_query}.*"
        result = list_models(model_regex=model_regex, limit=100)
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to search model cards: {str(e)}"
        )


@router.get("/search/advanced")
def advanced_search(
    name_regex: Optional[str] = Query(
        None, description="Regex pattern for model names"
    ),
    model_regex: Optional[str] = Query(
        None, description="Regex pattern for model card content"
    ),
    version_range: Optional[str] = Query(
        None, description="Version range specification"
    ),
    limit: int = Query(100, ge=1, le=1000),
):
    try:
        result = list_models(
            name_regex=name_regex,
            model_regex=model_regex,
            version_range=version_range,
            limit=limit,
        )
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to perform advanced search: {str(e)}"
        )


@router.get("")
def list_packages(
    limit: int = Query(100, ge=1, le=1000),
    continuation_token: str = Query(None),
    name_regex: str = Query(None, description="Regex to match model names"),
    model_regex: str = Query(None, description="Regex to match model cards"),
    version_range: str = Query(
        None,
        description="Version specification: exact (1.2.3), bounded (1.2.3-2.1.0), tilde (~1.2.0), or caret (^1.2.0)",
    ),
):
    try:
        result = list_models(
            name_regex=name_regex,
            model_regex=model_regex,
            version_range=version_range,
            limit=limit,
            continuation_token=continuation_token,
        )
        return {"packages": result["models"], "next_token": result["next_token"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list packages: {str(e)}"
        )


import boto3
import os
from datetime import datetime, timezone

# Initialize DynamoDB
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
PACKAGES_TABLE = os.getenv("DDB_TABLE_PACKAGES", "packages")

@router.post("/models/{model_id}/{version}/model.zip")
def upload_model_file(model_id: str, version: str, request: Request, file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    try:
        file_content = file.file.read()
        result = upload_model(file_content, model_id, version)
        
        # Store metadata in DynamoDB
        try:
            packages_table = dynamodb.Table(PACKAGES_TABLE)
            pkg_key = f"{model_id}/{version}"
            package_item = {
                "pkg_key": pkg_key,
                "pkg_name": model_id,
                "version": version,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "size_bytes": len(file_content),
                "sha256": result.get("sha256")
            }
            packages_table.put_item(Item=package_item)
        except Exception as e:
            print(f"Failed to store metadata in DynamoDB: {e}")
            # We don't fail the upload if metadata storage fails, but we log it
            
        # Log upload event for non-repudiation
        user_id = _get_user_id_from_request(request)
        log_upload_event(
            artifact_name=model_id,
            artifact_type="model",
            artifact_id=model_id,  # Using model_id as artifact_id for now
            user_id=user_id,
            version=version,
            status="success",
            reason="Model file uploaded successfully"
        )
            
        return result
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchBucket":
            raise HTTPException(status_code=500, detail="S3 bucket not found")
        elif error_code == "AccessDenied":
            raise HTTPException(status_code=500, detail="Access denied to S3 bucket")
        else:
            raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/models/{model_id}/{version}/model.zip")
def download_model_file(
    model_id: str,
    version: str,
    component: str = Query(
        "full", description="Component to download: 'full', 'weights', or 'datasets'"
    ),
):
    try:
        # Retrieve expected hash from DynamoDB
        expected_hash = None
        try:
            packages_table = dynamodb.Table(PACKAGES_TABLE)
            pkg_key = f"{model_id}/{version}"
            response = packages_table.get_item(Key={"pkg_key": pkg_key})
            if "Item" in response:
                expected_hash = response["Item"].get("sha256")
        except Exception as e:
            print(f"Failed to retrieve metadata from DynamoDB: {e}")

        file_content = download_model(model_id, version, component, expected_hash=expected_hash)
        return StreamingResponse(
            io.BytesIO(file_content),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={model_id}_{version}_{component}.zip"
            },
        )
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "NoSuchKey":
            raise HTTPException(
                status_code=404, detail=f"Model {model_id} version {version} not found"
            )
        elif error_code == "NoSuchBucket":
            raise HTTPException(status_code=500, detail="S3 bucket not found")
        elif error_code == "AccessDenied":
            raise HTTPException(status_code=500, detail="Access denied to S3 bucket")
        else:
            raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.post("/upload")
def upload_package(request: Request, file: UploadFile = File(...), debloat: bool = Query(False)):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only ZIP files are supported")
    try:
        filename = file.filename.replace(".zip", "")
        model_id = filename
        version = "1.0.0"
        file_content = file.file.read()
        result = upload_model(file_content, model_id, version, debloat)
        
        # Store metadata in DynamoDB
        try:
            packages_table = dynamodb.Table(PACKAGES_TABLE)
            pkg_key = f"{model_id}/{version}"
            package_item = {
                "pkg_key": pkg_key,
                "pkg_name": model_id,
                "version": version,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "size_bytes": len(file_content),
                "sha256": result.get("sha256")
            }
            packages_table.put_item(Item=package_item)
        except Exception as e:
            print(f"Failed to store metadata in DynamoDB: {e}")

        # Log upload event for non-repudiation
        user_id = _get_user_id_from_request(request)
        log_upload_event(
            artifact_name=model_id,
            artifact_type="model",
            artifact_id=model_id,
            user_id=user_id,
            version=version,
            status="success",
            reason="Package uploaded successfully"
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/reset")
def reset_system():
    try:
        result = reset_registry()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset system: {str(e)}")


@router.post("/sync-neptune")
def sync_neptune():
    try:
        result = sync_model_lineage_to_neptune()
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync Neptune: {str(e)}")


@router.get("/models/{model_id}/{version}/lineage")
def get_model_lineage_from_config_api(model_id: str, version: str):
    try:
        result = get_model_lineage_from_config(model_id, version)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get lineage: {str(e)}")


@router.get("/models/{model_id}/{version}/size")
def get_model_sizes_api(model_id: str, version: str):
    try:
        result = get_model_sizes(model_id, version)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get model sizes: {str(e)}"
        )


@router.post("/models/ingest")
def ingest_model(
    request: Request,
    model_id: str = Query(..., description="HuggingFace model ID to ingest"),
    version: str = Query("main", description="Model version/revision"),
):
    try:
        result = model_ingestion(model_id, version)
        
        # Log upload event
        user_id = _get_user_id_from_request(request)
        log_upload_event(
            artifact_name=model_id,
            artifact_type="model",
            artifact_id=model_id,
            user_id=user_id,
            version=version,
            status="success",
            reason="Model ingested successfully"
        )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest model: {str(e)}")
