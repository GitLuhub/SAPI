import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, String, Boolean, Enum
from sqlalchemy import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    username = Column(String(length=50), unique=True, nullable=False, index=True)
    email = Column(String(length=100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(length=255), nullable=False)
    full_name = Column(String(length=100), nullable=True)
    role = Column(Enum("admin", "document_reviewer", "user", name="userrole"), 
                  nullable=False, default="user")
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, 
                        nullable=False)

    documents = relationship("Document", back_populates="upload_user")
    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role})>"
