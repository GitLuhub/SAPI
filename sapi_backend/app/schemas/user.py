from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "admin"
    DOCUMENT_REVIEWER = "document_reviewer"
    USER = "user"


class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER


class UserCreate(UserBase):
    password: str


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserInDB(UserBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class User(UserInDB):
    hashed_password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserLogin(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# GDPR schemas
# ---------------------------------------------------------------------------

class AccountDeleteRequest(BaseModel):
    password: str


class ExtractedFieldExport(BaseModel):
    field_name: str
    field_label: Optional[str] = None
    ai_extracted_value: Optional[str] = None
    final_value: str
    is_corrected: bool
    corrected_at: Optional[datetime] = None


class DocumentExport(BaseModel):
    id: UUID
    original_filename: str
    status: str
    mime_type: Optional[str] = None
    file_size: Optional[str] = None
    created_at: datetime
    extracted_fields: List[ExtractedFieldExport] = []


class UserDataExport(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    created_at: datetime
    exported_at: datetime
    documents: List[DocumentExport] = []
