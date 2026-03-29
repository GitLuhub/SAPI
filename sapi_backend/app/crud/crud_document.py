from datetime import datetime, date
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.db.models.document import Document, DocumentType


class CRUDDocument:
    """Operaciones de base de datos para Document."""

    def get(self, db: Session, id: UUID) -> Optional[Document]:
        return db.query(Document).filter(Document.id == id).first()

    def add(self, db: Session, document: Document) -> None:
        """Agrega el documento a la sesión (sin commit). El endpoint gestiona la transacción."""
        db.add(document)

    def delete(self, db: Session, document: Document) -> None:
        """Elimina el documento de la sesión (sin commit)."""
        db.delete(document)

    def list_filtered(
        self,
        db: Session,
        *,
        status_filter: Optional[str] = None,
        document_type_id: Optional[UUID] = None,
        search_query: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        upload_user_id: Optional[UUID] = None,
        page: int = 1,
        size: int = 10,
    ) -> Tuple[List[Document], int]:
        """Devuelve (documentos, total) aplicando los filtros dados."""
        query = db.query(Document).options(joinedload(Document.document_type))

        if status_filter:
            query = query.filter(Document.status == status_filter)
        if document_type_id:
            query = query.filter(Document.document_type_id == document_type_id)
        if search_query:
            query = query.filter(Document.original_filename.ilike(f"%{search_query}%"))
        if date_from:
            query = query.filter(
                Document.created_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to:
            query = query.filter(
                Document.created_at <= datetime.combine(date_to, datetime.max.time())
            )
        if upload_user_id:
            query = query.filter(Document.upload_user_id == upload_user_id)

        total = query.count()
        offset = (page - 1) * size
        documents = query.order_by(Document.created_at.desc()).offset(offset).limit(size).all()
        return documents, total

    def get_type_by_id(self, db: Session, id: UUID) -> Optional[DocumentType]:
        return (
            db.query(DocumentType)
            .filter(DocumentType.id == id, DocumentType.is_active == True)
            .first()
        )

    def get_type_by_name(self, db: Session, name: str) -> Optional[DocumentType]:
        result = db.query(DocumentType).filter(DocumentType.name == name).first()
        if result:
            return result
        return (
            db.query(DocumentType)
            .filter(DocumentType.name.ilike(f"%{name}%"))
            .first()
        )

    def list_active_types(self, db: Session) -> List[DocumentType]:
        return db.query(DocumentType).filter(DocumentType.is_active == True).all()


crud_document = CRUDDocument()
