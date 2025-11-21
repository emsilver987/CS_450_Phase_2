import pytest
from unittest.mock import MagicMock, patch
from fastapi import UploadFile
from src.index import upload_post

@pytest.mark.asyncio
async def test_upload_streaming():
    # Mock Request
    request = MagicMock()
    
    # Mock UploadFile
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test_model.zip"
    # Mock the file attribute which is a SpooledTemporaryFile usually
    mock_file.file = MagicMock()
    
    # Mock dependencies
    with patch("src.index.shutil.copyfileobj") as mock_copy, \
         patch("src.index.tempfile.NamedTemporaryFile") as mock_temp, \
         patch("src.index.s3") as mock_s3, \
         patch("src.index.aws_available", True):
        
        # Setup mock temp file
        mock_temp_file = MagicMock()
        mock_temp.return_value.__enter__.return_value = mock_temp_file
        
        # Setup mock read for hash calculation (return empty bytes to stop iteration)
        mock_temp_file.read.side_effect = [b"chunk1", b"chunk2", b""]
        
        # Execute
        result = await upload_post(
            request=request,
            file=mock_file,
            model_id="test-model",
            version="1.0.0"
        )
        
        # Verify
        # 1. Check that copyfileobj was called (streaming to disk)
        mock_copy.assert_called_once_with(mock_file.file, mock_temp_file)
        
        # 2. Check that s3.put_object was called with the temp file object
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args[1]
        assert call_args["Bucket"] is not None
        assert call_args["Key"] == "models/test-model/1.0.0/model.zip"
        assert call_args["Body"] == mock_temp_file
        
        # 3. Check success response
        assert result["message"] == "Upload successful"
        assert "sha256_hash" in result["details"]

