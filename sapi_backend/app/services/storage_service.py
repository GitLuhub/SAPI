import os
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self):
        self.provider = settings.OBJECT_STORAGE_PROVIDER
        self.local_path = settings.LOCAL_STORAGE_PATH
        
        if self.provider == "AWS_S3":
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket_name = settings.OBJECT_STORAGE_BUCKET_NAME
        else:
            os.makedirs(self.local_path, exist_ok=True)
    
    async def upload_file(
        self, 
        path: str, 
        content: bytes, 
        content_type: Optional[str] = None
    ) -> str:
        if self.provider == "AWS_S3":
            try:
                extra_args = {}
                if content_type:
                    extra_args["ContentType"] = content_type
                
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=path,
                    Body=content,
                    **extra_args
                )
                logger.info(f"File uploaded to S3: {path}")
                return f"s3://{self.bucket_name}/{path}"
            except ClientError as e:
                logger.error(f"S3 upload error: {e}")
                raise
        
        local_file_path = os.path.join(self.local_path, path)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        
        with open(local_file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"File saved locally: {local_file_path}")
        return local_file_path
    
    async def download_file(self, path: str) -> bytes:
        if self.provider == "AWS_S3":
            if path.startswith("s3://"):
                path = path.replace(f"s3://{self.bucket_name}/", "")
            
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name,
                    Key=path
                )
                return response["Body"].read()
            except ClientError as e:
                logger.error(f"S3 download error: {e}")
                raise
        
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        
        local_file_path = os.path.join(self.local_path, path)
        if os.path.exists(local_file_path):
            with open(local_file_path, "rb") as f:
                return f.read()
        
        raise FileNotFoundError(f"File not found: {path}")
    
    async def delete_file(self, path: str) -> bool:
        if self.provider == "AWS_S3":
            if path.startswith("s3://"):
                path = path.replace(f"s3://{self.bucket_name}/", "")
            
            try:
                self.s3_client.delete_object(
                    Bucket=self.bucket_name,
                    Key=path
                )
                logger.info(f"File deleted from S3: {path}")
                return True
            except ClientError as e:
                logger.error(f"S3 delete error: {e}")
                return False
        
        local_file_path = os.path.join(self.local_path, path)
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
            logger.info(f"File deleted locally: {local_file_path}")
            return True
        
        return False
    
    def get_file_url(self, path: str, expires_in: int = 3600) -> str:
        if self.provider == "AWS_S3":
            if path.startswith("s3://"):
                path = path.replace(f"s3://{self.bucket_name}/", "")
            
            try:
                url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': path},
                    ExpiresIn=expires_in
                )
                return url
            except ClientError as e:
                logger.error(f"S3 presigned URL error: {e}")
                raise
        
        return f"/uploads/{path}"


storage_service = StorageService()
