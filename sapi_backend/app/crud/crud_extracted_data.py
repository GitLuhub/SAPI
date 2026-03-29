from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.extracted_data import ExtractedData


class CRUDExtractedData:
    """Operaciones de base de datos para ExtractedData."""

    def get_by_document(self, db: Session, document_id: UUID) -> List[ExtractedData]:
        return (
            db.query(ExtractedData)
            .filter(ExtractedData.document_id == document_id)
            .all()
        )

    def get_field(
        self, db: Session, document_id: UUID, field_name: str
    ) -> Optional[ExtractedData]:
        return (
            db.query(ExtractedData)
            .filter(
                ExtractedData.document_id == document_id,
                ExtractedData.field_name == field_name,
            )
            .first()
        )

    def count_uncorrected(self, db: Session, document_id: UUID) -> int:
        return (
            db.query(ExtractedData)
            .filter(
                ExtractedData.document_id == document_id,
                ExtractedData.is_corrected == False,
            )
            .count()
        )

    def add(self, db: Session, field: ExtractedData) -> None:
        """Agrega el campo a la sesión (sin commit)."""
        db.add(field)

    def update_field(
        self,
        db: Session,
        field: ExtractedData,
        new_value: str,
        corrected_by: UUID,
    ) -> None:
        """Actualiza los valores de un campo existente (sin commit)."""
        field.final_value = new_value
        field.is_corrected = True
        field.corrected_by_user_id = corrected_by
        field.corrected_at = datetime.utcnow()
        db.add(field)


crud_extracted_data = CRUDExtractedData()
