from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from enum import Enum


class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    REVIEW_NEEDED = "REVIEW_NEEDED"
    ERROR = "ERROR"


class DocumentTypeBase(BaseModel):
    name: str
    description: Optional[str] = None


class DocumentTypeCreate(DocumentTypeBase):
    pass


class DocumentTypeResponse(DocumentTypeBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DocumentBase(BaseModel):
    original_filename: str


class DocumentCreate(DocumentBase):
    document_type_id: Optional[UUID] = None


class DocumentUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    document_type_id: Optional[UUID] = None
    classification_confidence: Optional[str] = None
    executive_summary: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None


class ExtractedFieldResponse(BaseModel):
    field_name: str
    field_label: Optional[str] = None
    ai_extracted_value: Optional[str] = None
    ai_confidence: Optional[str] = None
    final_value: str
    is_corrected: bool
    corrected_at: Optional[datetime] = None

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    original_filename: str
    status: DocumentStatus
    classification_confidence: Optional[str] = None
    upload_user_id: UUID
    document_type_id: Optional[UUID] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    original_filename: str
    status: DocumentStatus
    document_type_name: Optional[str] = None
    classification_confidence: Optional[str] = None
    created_at: datetime


class DocumentStatusResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    message: str


class DocumentDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    original_filename: str
    file_size: Optional[str] = None
    mime_type: Optional[str] = None
    status: DocumentStatus
    document_type: Optional[DocumentTypeResponse] = None
    classification_confidence: Optional[str] = None
    executive_summary: Optional[str] = None
    extracted_fields: List[ExtractedFieldResponse] = []
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ExtractedDataUpdate(BaseModel):
    field_name: str
    new_value: str


class ExtractedDataUpdateList(BaseModel):
    updates: List[ExtractedDataUpdate]
