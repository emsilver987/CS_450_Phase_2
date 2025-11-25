from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import boto3
import uuid
import zipfile
import io
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import os
import logging
import json

# AWS clients
s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))

# Environment variables
ARTIFACTS_BUCKET = os.getenv("ARTIFACTS_BUCKET", "pkg-artifacts")
PACKAGES_TABLE = os.getenv("DDB_TABLE_PACKAGES", "packages")
UPLOADS_TABLE = os.getenv("DDB_TABLE_UPLOADS", "uploads")

app = FastAPI(title="Package Management Service", version="1.0.0")
security = HTTPBearer()


# Pydantic models
class UploadInitRequest(BaseModel):
    pkg_name: str
    version: str
    description: Optional[str] = None
    is_sensitive: bool = False
    allowed_groups: List[str] = []


class UploadInitResponse(BaseModel):
    upload_id: str
    expires_at: str


class UploadPartRequest(BaseModel):
    upload_id: str
    part_number: int


class UploadCommitRequest(BaseModel):
    upload_id: str
    parts: List[Dict[str, str]]  # [{"ETag": "...", "PartNumber": 1}, ...]


class PackageInfo(BaseModel):
    pkg_key: str
    pkg_name: str
    version: str
    description: Optional[str]
    is_sensitive: bool
    allowed_groups: List[str]
    created_at: str
    updated_at: str
    size_bytes: int


class DownloadUrlResponse(BaseModel):
    url: str
    expires_at: str


# Helper functions for package operations
def get_package_by_id(pkg_key: str) -> Optional[Dict[str, Any]]:
    """Get package by pkg_key (pkg_name/version)"""
    try:
        packages_table = dynamodb.Table(PACKAGES_TABLE)
        response = packages_table.get_item(Key={"pkg_key": pkg_key})
        if "Item" in response:
            return response["Item"]
        return None
    except Exception as e:
        logging.error(f"Error getting package {pkg_key}: {e}")
        return None


def search_packages(query: str) -> List[Dict[str, Any]]:
    """Search packages by name (case-insensitive partial match)"""
    try:
        packages_table = dynamodb.Table(PACKAGES_TABLE)
        response = packages_table.scan()
        
        results = []
        query_lower = query.lower()
        for item in response.get("Items", []):
            pkg_name = item.get("pkg_name", "").lower()
            if query_lower in pkg_name:
                results.append(item)
        
        return results
    except Exception as e:
        logging.error(f"Error searching packages: {e}")
        return []


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Verify JWT token and return user info"""
    # This would integrate with the auth service
    # For now, we'll assume token verification is handled by middleware
    return {"user_id": "demo_user", "groups": ["Group_106"]}


def validate_package_structure(file_content: bytes) -> Dict[str, Any]:
    """Validate package ZIP structure"""
    try:
        with zipfile.ZipFile(io.BytesIO(file_content), "r") as zip_file:
            file_list = zip_file.namelist()

            # Check for common package files
            has_package_json = any("package.json" in f for f in file_list)
            has_readme = any("README.md" in f or "readme.md" in f for f in file_list)
            has_src = any("src/" in f or "lib/" in f for f in file_list)

            return {
                "valid": True,
                "has_package_json": has_package_json,
                "has_readme": has_readme,
                "has_src": has_src,
                "file_count": len(file_list),
                "files": file_list[:10],  # First 10 files
            }
    except zipfile.BadZipFile:
        return {"valid": False, "error": "Invalid ZIP file"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


@app.post("/init", response_model=UploadInitResponse)
async def init_upload(
    request: UploadInitRequest, user: Dict[str, Any] = Depends(verify_token)
):
    """Initialize multipart upload"""
    try:
        upload_id = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Store upload metadata
        table = dynamodb.Table(UPLOADS_TABLE)
        upload_item = {
            "upload_id": upload_id,
            "pkg_name": request.pkg_name,
            "version": request.version,
            "description": request.description,
            "is_sensitive": request.is_sensitive,
            "allowed_groups": request.allowed_groups,
            "user_id": user["user_id"],
            "status": "initiated",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        table.put_item(Item=upload_item)

        return UploadInitResponse(
            upload_id=upload_id, expires_at=expires_at.isoformat()
        )

    except Exception as e:
        logging.error(f"Error initializing upload: {e}")
        raise HTTPException(status_code=500, detail="Error initializing upload")


@app.post("/part/{upload_id}")
async def upload_part(
    upload_id: str,
    part_number: int = Query(..., ge=1, le=10000),
    file: UploadFile = File(...),
    user: Dict[str, Any] = Depends(verify_token),
):
    """Upload a part of multipart upload"""
    try:
        # Get upload metadata
        table = dynamodb.Table(UPLOADS_TABLE)
        response = table.get_item(Key={"upload_id": upload_id})

        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Upload not found")

        upload_info = response["Item"]

        # Verify ownership
        if upload_info["user_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if upload is still valid
        expires_at = datetime.fromisoformat(
            upload_info["expires_at"].replace("Z", "+00:00")
        )
        if datetime.now(timezone.utc) > expires_at:
            raise HTTPException(status_code=410, detail="Upload expired")

        # Upload part to S3
        s3_key = f"packages/{upload_info['pkg_name']}/{upload_info['version']}/upload_{upload_id}/part_{part_number}"

        file_content = await file.read()
        response = s3.put_object(
            Bucket=ARTIFACTS_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type or "application/octet-stream",
        )

        return {
            "upload_id": upload_id,
            "part_number": part_number,
            "etag": response["ETag"].strip('"'),
            "size": len(file_content),
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error uploading part: {e}")
        raise HTTPException(status_code=500, detail="Error uploading part")


@app.post("/commit/{upload_id}")
async def commit_upload(
    upload_id: str,
    request: UploadCommitRequest,
    user: Dict[str, Any] = Depends(verify_token),
):
    """Commit multipart upload"""
    try:
        # Get upload metadata
        table = dynamodb.Table(UPLOADS_TABLE)
        response = table.get_item(Key={"upload_id": upload_id})

        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Upload not found")

        upload_info = response["Item"]

        # Verify ownership
        if upload_info["user_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Prepare multipart upload
        s3_key = (
            f"packages/{upload_info['pkg_name']}/{upload_info['version']}/package.zip"
        )

        # Create multipart upload
        multipart_response = s3.create_multipart_upload(
            Bucket=ARTIFACTS_BUCKET, Key=s3_key, ContentType="application/zip"
        )

        upload_id_s3 = multipart_response["UploadId"]

        # Copy parts
        parts = []
        for part_info in request.parts:
            part_number = int(part_info["PartNumber"])
            etag = part_info["ETag"]

            source_key = f"packages/{upload_info['pkg_name']}/{upload_info['version']}/upload_{upload_id}/part_{part_number}"

            # Copy part
            copy_response = s3.upload_part_copy(
                Bucket=ARTIFACTS_BUCKET,
                Key=s3_key,
                PartNumber=part_number,
                UploadId=upload_id_s3,
                CopySource={"Bucket": ARTIFACTS_BUCKET, "Key": source_key},
            )

            parts.append(
                {
                    "ETag": copy_response["CopyPartResult"]["ETag"],
                    "PartNumber": part_number,
                }
            )

        # Complete multipart upload
        s3.complete_multipart_upload(
            Bucket=ARTIFACTS_BUCKET,
            Key=s3_key,
            UploadId=upload_id_s3,
            MultipartUpload={"Parts": parts},
        )

        # Store package metadata
        packages_table = dynamodb.Table(PACKAGES_TABLE)
        pkg_key = f"{upload_info['pkg_name']}/{upload_info['version']}"

        package_item = {
            "pkg_key": pkg_key,
            "pkg_name": upload_info["pkg_name"],
            "version": upload_info["version"],
            "description": upload_info.get("description"),
            "is_sensitive": upload_info["is_sensitive"],
            "allowed_groups": upload_info["allowed_groups"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "size_bytes": sum(
                int(part["ETag"].split("-")[1]) for part in parts if "-" in part["ETag"]
            ),
        }

        packages_table.put_item(Item=package_item)

        # Update upload status
        table.update_item(
            Key={"upload_id": upload_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "completed",
                ":updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # Clean up temporary parts
        for part_info in request.parts:
            part_number = int(part_info["PartNumber"])
            source_key = f"packages/{upload_info['pkg_name']}/{upload_info['version']}/upload_{upload_id}/part_{part_number}"
            try:
                s3.delete_object(Bucket=ARTIFACTS_BUCKET, Key=source_key)
            except Exception as e:
                logging.warning(f"Failed to clean up part {source_key}: {e}")

        return {"message": "Upload completed successfully", "pkg_key": pkg_key}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error committing upload: {e}")
        raise HTTPException(status_code=500, detail="Error committing upload")


@app.post("/abort/{upload_id}")
async def abort_upload(upload_id: str, user: Dict[str, Any] = Depends(verify_token)):
    """Abort multipart upload"""
    try:
        # Get upload metadata
        table = dynamodb.Table(UPLOADS_TABLE)
        response = table.get_item(Key={"upload_id": upload_id})

        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Upload not found")

        upload_info = response["Item"]

        # Verify ownership
        if upload_info["user_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Update upload status
        table.update_item(
            Key={"upload_id": upload_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "aborted",
                ":updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        return {"message": "Upload aborted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error aborting upload: {e}")
        raise HTTPException(status_code=500, detail="Error aborting upload")


@app.get("/download/{pkg_name}/{version}", response_model=DownloadUrlResponse)
async def get_download_url(
    pkg_name: str,
    version: str,
    ttl_seconds: int = Query(300, ge=60, le=3600),
    user: Dict[str, Any] = Depends(verify_token),
):
    """Get presigned download URL"""
    try:
        # Get package metadata
        packages_table = dynamodb.Table(PACKAGES_TABLE)
        pkg_key = f"{pkg_name}/{version}"

        response = packages_table.get_item(Key={"pkg_key": pkg_key})
        if "Item" not in response:
            raise HTTPException(status_code=404, detail="Package not found")

        package = response["Item"]

        # Check access for sensitive packages
        if package.get("is_sensitive", False):
            allowed_groups = package.get("allowed_groups", [])
            user_groups = user.get("groups", [])

            if not any(group in user_groups for group in allowed_groups):
                raise HTTPException(status_code=403, detail="Access denied")

        # Generate presigned URL
        s3_key = f"packages/{pkg_name}/{version}/package.zip"

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": ARTIFACTS_BUCKET, "Key": s3_key},
            ExpiresIn=ttl_seconds,
        )

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        return DownloadUrlResponse(url=url, expires_at=expires_at.isoformat())

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating download URL: {e}")
        raise HTTPException(status_code=500, detail="Error generating download URL")


@app.get("/packages", response_model=List[PackageInfo])
async def list_packages(
    limit: int = Query(100, ge=1, le=1000),
    continuation_token: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(verify_token),
):
    """List packages"""
    try:
        packages_table = dynamodb.Table(PACKAGES_TABLE)

        # Simple scan for now - in production, you'd use pagination
        response = packages_table.scan(Limit=limit)

        packages = []
        for item in response.get("Items", []):
            packages.append(
                PackageInfo(
                    pkg_key=item["pkg_key"],
                    pkg_name=item["pkg_name"],
                    version=item["version"],
                    description=item.get("description"),
                    is_sensitive=item.get("is_sensitive", False),
                    allowed_groups=item.get("allowed_groups", []),
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    size_bytes=item.get("size_bytes", 0),
                )
            )

        return packages

    except Exception as e:
        logging.error(f"Error listing packages: {e}")
        raise HTTPException(status_code=500, detail="Error listing packages")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "3003"))
    uvicorn.run(app, host="0.0.0.0", port=port)


# Additional helper functions for test compatibility
def get_package_from_db(pkg_key: str) -> Optional[Dict[str, Any]]:
    """Get package from database by pkg_key (alias for get_package_by_id)"""
    return get_package_by_id(pkg_key)


def list_packages_from_db(limit: int = 100) -> List[Dict[str, Any]]:
    """List packages from database"""
    try:
        packages_table = dynamodb.Table(PACKAGES_TABLE)
        response = packages_table.scan(Limit=limit)
        return response.get("Items", [])
    except Exception as e:
        logging.error(f"Error listing packages: {e}")
        return []


def save_package_to_db(pkg_key_or_data: Any, package_data: Optional[Dict[str, Any]] = None) -> bool:
    """Save package to database (supports both old two-parameter and new single-parameter format)"""
    try:
        packages_table = dynamodb.Table(PACKAGES_TABLE)
        
        # Handle both old and new call signatures
        if package_data is not None:
            # Old format: save_package_to_db("p1", {"name": "package1"})
            # Merge pkg_key with data
            item = package_data.copy()
            if "pkg_key" not in item:
                item["pkg_key"] = str(pkg_key_or_data)
        else:
            # New format: save_package_to_db({"pkg_key": "p1", "name": "package1"})
            item = pkg_key_or_data
        
        packages_table.put_item(Item=item)
        return True
    except Exception as e:
        logging.error(f"Error saving package: {e}")
        return False

