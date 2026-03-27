import pytest
import os
from unittest.mock import patch
from app.services.storage_service import StorageService
import tempfile

@pytest.mark.asyncio
async def test_local_storage_upload_download():
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("app.core.config.settings.LOCAL_STORAGE_PATH", temp_dir), patch("app.core.config.settings.OBJECT_STORAGE_PROVIDER", "LOCAL"):
            service = StorageService()
        
        file_path = "test/doc.pdf"
        content = b"fake pdf content"
        
        # Test Upload
        url = await service.upload_file(file_path, content, "application/pdf")
        assert url is not None
        
        # Test Download
        downloaded = await service.download_file(file_path)
        assert downloaded == content
        
        # Test Delete
        await service.delete_file(file_path)
        assert not os.path.exists(os.path.join(temp_dir, file_path))
