import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.services.storage_service import StorageService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_local_service(temp_dir: str) -> StorageService:
    """Create a LOCAL storage service backed by a temp directory."""
    with patch("app.services.storage_service.settings") as mock_settings:
        mock_settings.OBJECT_STORAGE_PROVIDER = "LOCAL"
        mock_settings.LOCAL_STORAGE_PATH = temp_dir
        return StorageService()


def _make_s3_service() -> StorageService:
    """Create an AWS_S3 storage service with a mocked boto3 client."""
    with patch("app.services.storage_service.settings") as mock_settings:
        mock_settings.OBJECT_STORAGE_PROVIDER = "AWS_S3"
        mock_settings.LOCAL_STORAGE_PATH = "/tmp"
        mock_settings.OBJECT_STORAGE_BUCKET_NAME = "test-bucket"
        mock_settings.AWS_ACCESS_KEY_ID = "key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "secret"
        mock_settings.AWS_REGION = "us-east-1"
        with patch("boto3.client") as mock_boto:
            mock_boto.return_value = MagicMock()
            service = StorageService()
    service.bucket_name = "test-bucket"
    return service


# ---------------------------------------------------------------------------
# LOCAL storage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_local_storage_upload_download():
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _make_local_service(temp_dir)
        file_path = "test/doc.pdf"
        content = b"fake pdf content"

        url = await service.upload_file(file_path, content, "application/pdf")
        assert url is not None

        downloaded = await service.download_file(file_path)
        assert downloaded == content

        await service.delete_file(file_path)
        assert not os.path.exists(os.path.join(temp_dir, file_path))


@pytest.mark.asyncio
async def test_local_download_by_direct_path():
    """Covers lines 79-80: download when path itself exists on disk."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _make_local_service(temp_dir)
        direct_path = os.path.join(temp_dir, "direct.pdf")
        with open(direct_path, "wb") as f:
            f.write(b"direct content")

        downloaded = await service.download_file(direct_path)
        assert downloaded == b"direct content"


@pytest.mark.asyncio
async def test_local_download_file_not_found():
    """Covers line 87: raises FileNotFoundError when file doesn't exist anywhere."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _make_local_service(temp_dir)
        with pytest.raises(FileNotFoundError):
            await service.download_file("nonexistent/path.pdf")


@pytest.mark.asyncio
async def test_local_delete_not_found_returns_false():
    """Covers line 111: delete returns False when local file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _make_local_service(temp_dir)
        result = await service.delete_file("ghost/file.pdf")
        assert result is False


def test_local_get_file_url():
    """Covers line 129: LOCAL get_file_url returns /uploads/ path."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = _make_local_service(temp_dir)
        url = service.get_file_url("subdir/file.pdf")
        assert url == "/uploads/subdir/file.pdf"


# ---------------------------------------------------------------------------
# S3 storage — init
# ---------------------------------------------------------------------------

def test_s3_storage_init():
    """Covers lines 20-26: S3 client is created during __init__."""
    service = _make_s3_service()
    assert service.provider == "AWS_S3"
    assert service.bucket_name == "test-bucket"
    assert service.s3_client is not None


# ---------------------------------------------------------------------------
# S3 storage — upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s3_upload_with_content_type():
    """Covers lines 37-49: S3 upload success with content_type."""
    service = _make_s3_service()
    service.s3_client.put_object.return_value = {}

    url = await service.upload_file("docs/invoice.pdf", b"pdf bytes", "application/pdf")

    assert url == "s3://test-bucket/docs/invoice.pdf"
    service.s3_client.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="docs/invoice.pdf",
        Body=b"pdf bytes",
        ContentType="application/pdf",
    )


@pytest.mark.asyncio
async def test_s3_upload_without_content_type():
    """Covers lines 37-49: S3 upload success without content_type."""
    service = _make_s3_service()
    service.s3_client.put_object.return_value = {}

    url = await service.upload_file("docs/file.bin", b"data")

    assert url == "s3://test-bucket/docs/file.bin"
    call_kwargs = service.s3_client.put_object.call_args[1]
    assert "ContentType" not in call_kwargs


@pytest.mark.asyncio
async def test_s3_upload_client_error_raises():
    """Covers lines 50-52: S3 ClientError is propagated."""
    service = _make_s3_service()
    error_response = {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}}
    service.s3_client.put_object.side_effect = ClientError(error_response, "PutObject")

    with pytest.raises(ClientError):
        await service.upload_file("docs/file.pdf", b"content")


# ---------------------------------------------------------------------------
# S3 storage — download
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s3_download_success():
    """Covers lines 65-73: S3 download without s3:// prefix."""
    service = _make_s3_service()
    mock_body = MagicMock()
    mock_body.read.return_value = b"s3 content"
    service.s3_client.get_object.return_value = {"Body": mock_body}

    result = await service.download_file("docs/invoice.pdf")

    assert result == b"s3 content"
    service.s3_client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="docs/invoice.pdf"
    )


@pytest.mark.asyncio
async def test_s3_download_with_s3_prefix():
    """Covers line 65-66: strips s3:// prefix before calling get_object."""
    service = _make_s3_service()
    mock_body = MagicMock()
    mock_body.read.return_value = b"prefixed content"
    service.s3_client.get_object.return_value = {"Body": mock_body}

    result = await service.download_file("s3://test-bucket/docs/invoice.pdf")

    assert result == b"prefixed content"
    service.s3_client.get_object.assert_called_once_with(
        Bucket="test-bucket", Key="docs/invoice.pdf"
    )


@pytest.mark.asyncio
async def test_s3_download_client_error_raises():
    """Covers lines 74-76: S3 ClientError on download is propagated."""
    service = _make_s3_service()
    error_response = {"Error": {"Code": "NoSuchKey", "Message": "Key not found"}}
    service.s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

    with pytest.raises(ClientError):
        await service.download_file("docs/missing.pdf")


# ---------------------------------------------------------------------------
# S3 storage — delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_s3_delete_success():
    """Covers lines 91-100: S3 delete success."""
    service = _make_s3_service()
    service.s3_client.delete_object.return_value = {}

    result = await service.delete_file("docs/old.pdf")

    assert result is True
    service.s3_client.delete_object.assert_called_once_with(
        Bucket="test-bucket", Key="docs/old.pdf"
    )


@pytest.mark.asyncio
async def test_s3_delete_with_s3_prefix():
    """Covers lines 91-92: strips s3:// prefix before delete."""
    service = _make_s3_service()
    service.s3_client.delete_object.return_value = {}

    result = await service.delete_file("s3://test-bucket/docs/old.pdf")

    assert result is True
    service.s3_client.delete_object.assert_called_once_with(
        Bucket="test-bucket", Key="docs/old.pdf"
    )


@pytest.mark.asyncio
async def test_s3_delete_client_error_returns_false():
    """Covers lines 101-103: S3 ClientError on delete returns False."""
    service = _make_s3_service()
    error_response = {"Error": {"Code": "AccessDenied", "Message": "Forbidden"}}
    service.s3_client.delete_object.side_effect = ClientError(error_response, "DeleteObject")

    result = await service.delete_file("docs/protected.pdf")

    assert result is False


# ---------------------------------------------------------------------------
# S3 storage — get_file_url
# ---------------------------------------------------------------------------

def test_s3_get_file_url_success():
    """Covers lines 114-124: S3 presigned URL generation."""
    service = _make_s3_service()
    service.s3_client.generate_presigned_url.return_value = "https://s3.amazonaws.com/presigned"

    url = service.get_file_url("docs/invoice.pdf")

    assert url == "https://s3.amazonaws.com/presigned"
    service.s3_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "docs/invoice.pdf"},
        ExpiresIn=3600,
    )


def test_s3_get_file_url_with_s3_prefix():
    """Covers lines 115-116: strips s3:// prefix before generating presigned URL."""
    service = _make_s3_service()
    service.s3_client.generate_presigned_url.return_value = "https://presigned"

    url = service.get_file_url("s3://test-bucket/docs/file.pdf")

    assert url == "https://presigned"
    service.s3_client.generate_presigned_url.assert_called_once_with(
        "get_object",
        Params={"Bucket": "test-bucket", "Key": "docs/file.pdf"},
        ExpiresIn=3600,
    )


def test_s3_get_file_url_client_error_raises():
    """Covers lines 125-127: S3 ClientError on presigned URL is propagated."""
    service = _make_s3_service()
    error_response = {"Error": {"Code": "InvalidParameter", "Message": "Error"}}
    service.s3_client.generate_presigned_url.side_effect = ClientError(
        error_response, "GeneratePresignedUrl"
    )

    with pytest.raises(ClientError):
        service.get_file_url("docs/file.pdf")
