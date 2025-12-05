"""
RDS PostgreSQL storage backend for model files.

This module provides RDS-based storage for model files using PostgreSQL BYTEA.
Designed for simple, non-scalable storage of up to 500 models.
"""
import os
import json
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor, Json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# RDS connection configuration
# Hardcoded values (can be overridden by environment variables)
# Values from infra/envs/dev/main.tf and infra/modules/rds/
RDS_DATABASE = os.getenv("RDS_DATABASE", "acme")  # From infra/modules/rds/variables.tf
RDS_USERNAME = os.getenv("RDS_USERNAME", "acme")  # From infra/modules/rds/variables.tf
RDS_PASSWORD = os.getenv("RDS_PASSWORD", "acme_rds_password_123")  # From infra/envs/dev/main.tf line 108
RDS_PORT = os.getenv("RDS_PORT", "5432")  # Default PostgreSQL port
# RDS endpoint - get from env var, default to localhost for local development
# For AWS: get from Terraform output: terraform output -state=infra/envs/dev/terraform.tfstate rds_address
# For local: use localhost (requires local PostgreSQL running)
RDS_ENDPOINT = os.getenv("RDS_ENDPOINT", "https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod/acme-rds.cc7q0ouesr1m.us-east-1.rds.amazonaws.com")

# Parse port from endpoint if it includes port
if RDS_ENDPOINT and ":" in RDS_ENDPOINT:
    host, port = RDS_ENDPOINT.rsplit(":", 1)
    RDS_ENDPOINT = host
    RDS_PORT = port

# Connection pool configuration
CONNECTION_POOL_MIN = 5
CONNECTION_POOL_MAX = 20

# Global connection pool
_connection_pool: Optional[pool.ThreadedConnectionPool] = None


def get_connection_pool() -> pool.ThreadedConnectionPool:
    """Get or create the RDS connection pool."""
    global _connection_pool
    
    if _connection_pool is None:
        if not RDS_ENDPOINT or not RDS_PASSWORD:
            raise HTTPException(
                status_code=503,
                detail="RDS configuration missing. Set RDS_ENDPOINT and RDS_PASSWORD environment variables.",
            )
        
        try:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=CONNECTION_POOL_MIN,
                maxconn=CONNECTION_POOL_MAX,
                host=RDS_ENDPOINT,
                port=RDS_PORT,
                database=RDS_DATABASE,
                user=RDS_USERNAME,
                password=RDS_PASSWORD,
            )
            logger.info(f"RDS connection pool created: {RDS_ENDPOINT}/{RDS_DATABASE}")
            
            # Initialize schema on first connection
            _initialize_schema()
        except Exception as e:
            logger.error(f"Failed to create RDS connection pool: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to connect to RDS: {str(e)}",
            )
    
    return _connection_pool


def _initialize_schema():
    """Initialize database schema if it doesn't exist."""
    conn = None
    try:
        pool = get_connection_pool()
        conn = pool.getconn()
        cursor = conn.cursor()
        
        # Create table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model_files (
                model_id VARCHAR(255) NOT NULL,
                version VARCHAR(100) NOT NULL,
                component VARCHAR(50) NOT NULL DEFAULT 'full',
                path_prefix VARCHAR(50) DEFAULT 'models',
                file_data BYTEA NOT NULL,
                file_size BIGINT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (model_id, version, component, path_prefix)
            );
        """)
        
        # Create artifact_metadata table for storing metadata (not binary files)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifact_metadata (
                artifact_id VARCHAR(255) NOT NULL PRIMARY KEY,
                name VARCHAR(500) NOT NULL,
                type VARCHAR(50) NOT NULL,
                version VARCHAR(100) NOT NULL,
                url TEXT,
                stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json JSONB
            );
        """)
        
        # Create indexes for artifact_metadata
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_artifact_name 
            ON artifact_metadata(name);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_artifact_type 
            ON artifact_metadata(type);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_artifact_name_type 
            ON artifact_metadata(name, type);
        """)
        
        # Create index if it doesn't exist
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_model_version 
            ON model_files(model_id, version);
        """)
        
        conn.commit()
        logger.info("RDS schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RDS schema: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            pool.putconn(conn)


def upload_model(
    file_content: bytes, model_id: str, version: str, use_performance_path: bool = False
) -> Dict[str, str]:
    """Upload a model file to RDS.
    
    Args:
        file_content: Model file content as bytes
        model_id: Model identifier
        version: Model version
        use_performance_path: If True, use 'performance' path prefix, otherwise 'models'
        
    Returns:
        Dictionary with upload status
        
    Raises:
        HTTPException: If upload fails
    """
    if not file_content or len(file_content) == 0:
        raise HTTPException(status_code=400, detail="Cannot upload empty file content")
    
    path_prefix = "performance" if use_performance_path else "models"
    component = "full"  # Default component
    
    conn = None
    try:
        pool = get_connection_pool()
        conn = pool.getconn()
        cursor = conn.cursor()
        
        # Insert or update model file
        cursor.execute("""
            INSERT INTO model_files (model_id, version, component, path_prefix, file_data, file_size)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (model_id, version, component, path_prefix)
            DO UPDATE SET
                file_data = EXCLUDED.file_data,
                file_size = EXCLUDED.file_size,
                created_at = CURRENT_TIMESTAMP
        """, (model_id, version, component, path_prefix, psycopg2.Binary(file_content), len(file_content)))
        
        conn.commit()
        logger.info(
            f"RDS upload successful: {model_id} v{version} ({len(file_content)} bytes) -> {path_prefix}/"
        )
        return {"message": "Upload successful", "path": f"{path_prefix}/{model_id}/{version}"}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"RDS upload failed for {model_id} v{version}: {error_msg}", exc_info=True)
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"RDS upload failed: {error_msg}")
    finally:
        if conn:
            pool.putconn(conn)


def download_model(
    model_id: str, version: str, component: str = "full", use_performance_path: bool = False
) -> bytes:
    """Download a model file from RDS.
    
    Args:
        model_id: Model identifier
        version: Model version
        component: Component to download ('full', 'weights', 'datasets')
        use_performance_path: If True, use 'performance' path prefix, otherwise 'models'
        
    Returns:
        Model file content as bytes
        
    Raises:
        HTTPException: If download fails or model not found
    """
    path_prefix = "performance" if use_performance_path else "models"
    
    conn = None
    try:
        pool = get_connection_pool()
        conn = pool.getconn()
        cursor = conn.cursor()
        
        # Query model file
        cursor.execute("""
            SELECT file_data, file_size
            FROM model_files
            WHERE model_id = %s AND version = %s AND component = %s AND path_prefix = %s
        """, (model_id, version, component, path_prefix))
        
        result = cursor.fetchone()
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Model {model_id} version {version} not found in RDS ({path_prefix}/)",
            )
        
        file_data, file_size = result
        
        logger.info(
            f"RDS download successful: {model_id} v{version} ({component}) from {path_prefix}/ ({file_size} bytes)"
        )
        return bytes(file_data)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"RDS download failed for {model_id} v{version}: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"RDS download failed: {error_msg}")
    finally:
        if conn:
            pool.putconn(conn)


def model_exists(
    model_id: str, version: str, component: str = "full", use_performance_path: bool = False
) -> bool:
    """Check if a model exists in RDS.
    
    Args:
        model_id: Model identifier
        version: Model version
        component: Component to check
        use_performance_path: If True, use 'performance' path prefix, otherwise 'models'
        
    Returns:
        True if model exists, False otherwise
    """
    path_prefix = "performance" if use_performance_path else "models"
    
    conn = None
    try:
        pool = get_connection_pool()
        conn = pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 1
            FROM model_files
            WHERE model_id = %s AND version = %s AND component = %s AND path_prefix = %s
            LIMIT 1
        """, (model_id, version, component, path_prefix))
        
        return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"RDS model_exists check failed for {model_id} v{version}: {e}")
        return False
    finally:
        if conn:
            pool.putconn(conn)


def store_artifact_metadata(
    artifact_id: str, artifact_name: str, artifact_type: str, version: str, url: str
) -> Dict[str, str]:
    """
    Store artifact metadata in RDS for all artifact types (model, dataset, code).
    This stores only metadata, not the actual binary files.
    
    Args:
        artifact_id: Unique artifact identifier
        artifact_name: Name of the artifact
        artifact_type: Type of artifact ('model', 'dataset', 'code')
        version: Version of the artifact
        url: URL of the artifact
        
    Returns:
        Dictionary with status and details
    """
    if not RDS_ENDPOINT or not RDS_PASSWORD:
        return {"status": "skipped", "reason": "RDS not available"}
    
    try:
        # Prepare metadata JSON
        metadata = {
            "artifact_id": artifact_id,
            "name": artifact_name,
            "type": artifact_type,
            "version": version,
            "url": url,
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        
        conn = None
        try:
            pool = get_connection_pool()
            conn = pool.getconn()
            cursor = conn.cursor()
            
            # Insert or update metadata
            cursor.execute("""
                INSERT INTO artifact_metadata (artifact_id, name, type, version, url, metadata_json)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (artifact_id)
                DO UPDATE SET
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    version = EXCLUDED.version,
                    url = EXCLUDED.url,
                    metadata_json = EXCLUDED.metadata_json,
                    stored_at = CURRENT_TIMESTAMP
            """, (
                artifact_id,
                artifact_name,
                artifact_type,
                version,
                url,
                Json(metadata)
            ))
            
            conn.commit()
            logger.info(
                f"DEBUG: ✅✅✅ Successfully stored artifact metadata to RDS: "
                f"artifact_id='{artifact_id}', name='{artifact_name}', type='{artifact_type}'"
            )
            logger.info(f"DEBUG: Metadata includes: artifact_id='{artifact_id}', name='{artifact_name}', type='{artifact_type}'")
            return {"status": "success", "artifact_id": artifact_id}
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                pool.putconn(conn)
    except Exception as e:
        logger.error(f"Failed to store artifact metadata in RDS: {str(e)}", exc_info=True)
        return {"status": "error", "error": str(e)}


def find_artifact_metadata_by_id(artifact_id: str) -> Optional[Dict[str, Any]]:
    """
    Find artifact metadata by artifact_id in RDS.
    
    Args:
        artifact_id: Artifact identifier to search for
        
    Returns:
        Dictionary with artifact metadata if found, None otherwise
    """
    if not RDS_ENDPOINT or not RDS_PASSWORD:
        return None
    
    conn = None
    try:
        pool = get_connection_pool()
        conn = pool.getconn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT artifact_id, name, type, version, url, metadata_json, stored_at
            FROM artifact_metadata
            WHERE artifact_id = %s
        """, (artifact_id,))
        
        result = cursor.fetchone()
        if result:
            # Convert RealDictRow to regular dict
            metadata = dict(result)
            # If metadata_json exists, use it; otherwise construct from fields
            if metadata.get("metadata_json"):
                return dict(metadata["metadata_json"])
            else:
                return {
                    "artifact_id": metadata.get("artifact_id"),
                    "name": metadata.get("name"),
                    "type": metadata.get("type"),
                    "version": metadata.get("version"),
                    "url": metadata.get("url"),
                }
        return None
    except Exception as e:
        logger.error(f"Failed to find artifact metadata in RDS: {str(e)}", exc_info=True)
        return None
    finally:
        if conn:
            pool.putconn(conn)

