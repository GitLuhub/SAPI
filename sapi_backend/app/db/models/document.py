import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class DocumentType(Base):
    __tablename__ = "document_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(length=100), unique=True, nullable=False, index=True)
    description = Column(String(length=500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, 
                        nullable=False)

    documents = relationship("Document", back_populates="document_type")

    def __repr__(self) -> str:
        return f"<DocumentType(id={self.id}, name={self.name})>"


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    original_filename = Column(String(length=255), nullable=False)
    storage_path = Column(String(length=500), nullable=False)
    file_size = Column(String(length=50), nullable=True)
    mime_type = Column(String(length=100), nullable=True)
    
    status = Column(
        String(length=50), 
        nullable=False, 
        default="UPLOADED",
        index=True
    )
    
    upload_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    document_type_id = Column(UUID(as_uuid=True), ForeignKey("document_types.id"), nullable=True, index=True)
    classification_confidence = Column(String(length=10), nullable=True)
    
    executive_summary = Column(String(length=2000), nullable=True)
    
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processing_error = Column(String(length=1000), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, 
                        nullable=False)

    upload_user = relationship("User", back_populates="documents")
    document_type = relationship("DocumentType", back_populates="documents")
    extracted_data = relationship("ExtractedData", back_populates="document", 
                                  cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.original_filename}, status={self.status})>"
