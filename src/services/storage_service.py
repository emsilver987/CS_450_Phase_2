"""
Storage abstraction layer for model file storage backends.

This module provides a unified interface for different storage backends (S3, RDS, etc.)
while maintaining backward compatibility with existing code.
"""
import os
import logging
from typing import Dict, Any, Protocol
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Storage backend configuration
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "s3").lower()


class StorageBackend(Protocol):
    """Protocol defining the interface for storage backends."""
    
    def download_model(
        self, model_id: str, version: str, component: str = "full", use_performance_path: bool = False
    ) -> bytes:
        """Download a model file from storage.
        
        Args:
            model_id: Model identifier
            version: Model version
            component: Component to download ('full', 'weights', 'datasets')
            use_performance_path: If True, use performance/ path prefix
            
        Returns:
            Model file content as bytes
            
        Raises:
            HTTPException: If download fails
        """
        ...
    
    def upload_model(
        self, file_content: bytes, model_id: str, version: str, use_performance_path: bool = False
    ) -> Dict[str, str]:
        """Upload a model file to storage.
        
        Args:
            file_content: Model file content as bytes
            model_id: Model identifier
            version: Model version
            use_performance_path: If True, use performance/ path prefix
            
        Returns:
            Dictionary with upload status
            
        Raises:
            HTTPException: If upload fails
        """
        ...


class S3StorageBackend:
    """S3 storage backend implementation."""
    
    def __init__(self):
        # Import S3 functions here to avoid circular imports
        from .s3_service import download_model as s3_download, upload_model as s3_upload
        self._download_model = s3_download
        self._upload_model = s3_upload
    
    def download_model(
        self, model_id: str, version: str, component: str = "full", use_performance_path: bool = False
    ) -> bytes:
        """Download model from S3."""
        return self._download_model(model_id, version, component, use_performance_path)
    
    def upload_model(
        self, file_content: bytes, model_id: str, version: str, use_performance_path: bool = False
    ) -> Dict[str, str]:
        """Upload model to S3.
        
        Note: S3 upload_model signature is (file_content, model_id, version, debloat=False)
        and doesn't support use_performance_path. Performance path uploads are handled
        separately in populate_registry.py via direct S3 calls.
        """
        # S3 upload_model always uses models/ path, performance/ path is handled separately
        return self._upload_model(file_content, model_id, version, debloat=False)


class RDSStorageBackend:
    """RDS PostgreSQL storage backend implementation."""
    
    def __init__(self):
        from .rds_service import download_model as rds_download, upload_model as rds_upload
        self._download_model = rds_download
        self._upload_model = rds_upload
    
    def download_model(
        self, model_id: str, version: str, component: str = "full", use_performance_path: bool = False
    ) -> bytes:
        """Download model from RDS."""
        return self._download_model(model_id, version, component, use_performance_path)
    
    def upload_model(
        self, file_content: bytes, model_id: str, version: str, use_performance_path: bool = False
    ) -> Dict[str, str]:
        """Upload model to RDS."""
        return self._upload_model(file_content, model_id, version, use_performance_path)


# Global storage backend instance (lazy initialization)
_storage_backend: StorageBackend | None = None


def get_storage_backend() -> StorageBackend:
    """Get the configured storage backend instance.
    
    Returns:
        StorageBackend instance based on STORAGE_BACKEND environment variable
    """
    global _storage_backend
    
    if _storage_backend is None:
        if STORAGE_BACKEND == "rds":
            logger.info("Initializing RDS storage backend")
            _storage_backend = RDSStorageBackend()
        else:
            logger.info("Initializing S3 storage backend (default)")
            _storage_backend = S3StorageBackend()
    
    return _storage_backend


# Convenience functions that match existing S3 function signatures
def download_model(
    model_id: str, version: str, component: str = "full", use_performance_path: bool = False
) -> bytes:
    """Download model from configured storage backend.
    
    This function maintains the same signature as the original s3_service.download_model
    to ensure backward compatibility.
    """
    backend = get_storage_backend()
    return backend.download_model(model_id, version, component, use_performance_path)


def upload_model(
    file_content: bytes, model_id: str, version: str, use_performance_path: bool = False
) -> Dict[str, str]:
    """Upload model to configured storage backend.
    
    This function provides a unified interface for uploading models.
    Note: S3 backend's upload_model doesn't support use_performance_path yet,
    but RDS backend does.
    """
    backend = get_storage_backend()
    return backend.upload_model(file_content, model_id, version, use_performance_path)

