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
        # Enforce SSE-KMS encryption for tampering protection
        kms_key_arn = os.getenv("KMS_KEY_ARN", "")
        put_params = {
            "Bucket": ARTIFACTS_BUCKET,
            "Key": s3_key,
            "Body": file_content,
            "ContentType": file.content_type or "application/octet-stream",
        }
        if kms_key_arn:
            put_params["ServerSideEncryption"] = "aws:kms"
            put_params["SSEKMSKeyId"] = kms_key_arn
        response = s3.put_object(**put_params)

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

        # Create multipart upload with SSE-KMS encryption
        kms_key_arn = os.getenv("KMS_KEY_ARN", "")
        multipart_params = {
            "Bucket": ARTIFACTS_BUCKET,
            "Key": s3_key,
            "ContentType": "application/zip"
        }
        if kms_key_arn:
            multipart_params["ServerSideEncryption"] = "aws:kms"
            multipart_params["SSEKMSKeyId"] = kms_key_arn
        multipart_response = s3.create_multipart_upload(**multipart_params)

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

        # Store package metadata with conditional write to prevent tampering
        packages_table = dynamodb.Table(PACKAGES_TABLE)
        pkg_key = f"{upload_info['pkg_name']}/{upload_info['version']}"
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Check if package already exists to get current updated_at
        existing_response = packages_table.get_item(Key={"pkg_key": pkg_key})
        existing_item = existing_response.get("Item")
        
        package_item = {
            "pkg_key": pkg_key,
            "pkg_name": upload_info["pkg_name"],
            "version": upload_info["version"],
            "description": upload_info.get("description"),
            "is_sensitive": upload_info["is_sensitive"],
            "allowed_groups": upload_info["allowed_groups"],
            "size_bytes": sum(
                int(part["ETag"].split("-")[1]) for part in parts if "-" in part["ETag"]
            ),
        }
        
        if existing_item:
            # Update existing package - use conditional write to prevent overwriting newer data
            existing_updated_at = existing_item.get("updated_at")
            package_item["created_at"] = existing_item.get("created_at", now_iso)
            package_item["updated_at"] = now_iso
            
            # Conditional write: only update if updated_at hasn't changed (prevents race conditions)
            try:
                packages_table.put_item(
                    Item=package_item,
                    ConditionExpression="updated_at = :existing_updated_at",
                    ExpressionAttributeValues={":existing_updated_at": existing_updated_at}
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    raise HTTPException(
                        status_code=409,
                        detail="Package was modified by another request. Please retry."
                    )
                raise
        else:
            # Create new package - use conditional write to prevent duplicate creation
            package_item["created_at"] = now_iso
            package_item["updated_at"] = now_iso
            
            # Conditional write: only create if package doesn't exist
            try:
                packages_table.put_item(
                    Item=package_item,
                    ConditionExpression="attribute_not_exists(pkg_key)"
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    raise HTTPException(
                        status_code=409,
                        detail="Package already exists. Use update operation instead."
                    )
                raise

        # Update upload status with conditional write to prevent tampering
        now_iso = datetime.now(timezone.utc).isoformat()
        existing_status = upload_info.get("status")
        table.update_item(
            Key={"upload_id": upload_id},
            UpdateExpression="SET #status = :status, updated_at = :updated_at",
            ConditionExpression="#status = :existing_status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "completed",
                ":updated_at": now_iso,
                ":existing_status": existing_status,
            },
        )

        # Log upload event for audit trail (non-repudiation)
        DOWNLOADS_TABLE = os.getenv("DDB_TABLE_DOWNLOADS", "downloads")
        try:
            audit_table = dynamodb.Table(DOWNLOADS_TABLE)
            event_id = f"{user['user_id']}_{upload_info['pkg_name']}_{upload_info['version']}_{now_iso}"
            audit_item = {
                "event_id": event_id,
                "pkg_name": upload_info["pkg_name"],
                "version": upload_info["version"],
                "user_id": user["user_id"],
                "timestamp": now_iso,
                "status": "uploaded",
                "reason": "Package upload completed",
                "validation_result": {},
            }
            audit_table.put_item(Item=audit_item)
        except Exception as e:
            logging.warning(f"Failed to log upload event: {e}")

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
    ttl_seconds: int = Query(300, ge=60, le=300),
    user: Dict[str, Any] = Depends(verify_token),
):
    """Get presigned download URL
    
    TTL is limited to 300 seconds (5 minutes) maximum to prevent information disclosure
    through intercepted or guessed presigned URLs.
    """
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

        # Generate presigned URL with TTL limited to 300 seconds for security
        # Short TTL limits exposure time if URL is intercepted or guessed
        s3_key = f"packages/{pkg_name}/{version}/package.zip"
        # Enforce maximum TTL of 300 seconds
        effective_ttl = min(ttl_seconds, 300)

        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": ARTIFACTS_BUCKET, "Key": s3_key},
            ExpiresIn=effective_ttl,
        )

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=effective_ttl)

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
