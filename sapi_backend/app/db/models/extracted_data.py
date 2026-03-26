import uuid
from datetime import datetime

from sqlalchemy import Column, String, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class ExtractedData(Base):
    __tablename__ = "extracted_data"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), 
                         nullable=False, index=True)
    field_name = Column(String(length=100), nullable=False)
    field_label = Column(String(length=200), nullable=True)
    
    ai_extracted_value = Column(String(length=1000), nullable=True)
    ai_confidence = Column(String(length=10), nullable=True)
    
    final_value = Column(String(length=1000), nullable=False)
    
    is_corrected = Column(Boolean, default=False, nullable=False)
    corrected_by_user_id = Column(UUID(as_uuid=True), nullable=True)
    corrected_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, 
                        nullable=False)

    document = relationship("Document", back_populates="extracted_data")

    def __repr__(self) -> str:
        return f"<ExtractedData(id={self.id}, field_name={self.field_name}, document_id={self.document_id})>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), 
                     nullable=True, index=True)
    action = Column(String(length=255), nullable=False)
    entity_type = Column(String(length=100), nullable=True)
    entity_id = Column(String(length=100), nullable=True)
    details = Column(String(length=2000), nullable=True)
    ip_address = Column(String(length=50), nullable=True)
    user_agent = Column(String(length=500), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id})>"
