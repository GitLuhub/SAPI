"""Tests unitarios para CRUDExtractedData."""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

import pytest

from app.crud.crud_extracted_data import CRUDExtractedData
from app.db.models.document import Document
from app.db.models.extracted_data import ExtractedData
from app.db.models.user import User
from app.core.security import get_password_hash


crud = CRUDExtractedData()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(db: Session) -> User:
    u = User(
        username=f"u_{uuid.uuid4().hex[:6]}",
        email=f"{uuid.uuid4().hex[:6]}@test.com",
        hashed_password=get_password_hash("pass"),
        role="user",
        is_active=True,
    )
    db.add(u)
    db.flush()
    return u


def _doc(db: Session, user: User) -> Document:
    d = Document(
        original_filename="test.pdf",
        storage_path="docs/test.pdf",
        file_size="1024",
        mime_type="application/pdf",
        status="PROCESSED",
        upload_user_id=user.id,
    )
    db.add(d)
    db.flush()
    return d


def _field(db: Session, doc: Document, field_name: str, is_corrected=False) -> ExtractedData:
    ef = ExtractedData(
        document_id=doc.id,
        field_name=field_name,
        field_label=field_name.replace("_", " ").title(),
        ai_extracted_value="valor_ai",
        ai_confidence=0.9,
        final_value="valor_ai",
        is_corrected=is_corrected,
    )
    db.add(ef)
    db.flush()
    return ef


# ---------------------------------------------------------------------------
# get_by_document
# ---------------------------------------------------------------------------

def test_get_by_document_returns_fields(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    _field(db_session, doc, "campo_uno")
    _field(db_session, doc, "campo_dos")
    db_session.commit()

    fields = crud.get_by_document(db_session, doc.id)
    assert len(fields) == 2
    names = {f.field_name for f in fields}
    assert "campo_uno" in names
    assert "campo_dos" in names


def test_get_by_document_empty(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    db_session.commit()

    fields = crud.get_by_document(db_session, doc.id)
    assert fields == []


# ---------------------------------------------------------------------------
# get_field
# ---------------------------------------------------------------------------

def test_get_field_found(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    _field(db_session, doc, "numero_factura")
    db_session.commit()

    found = crud.get_field(db_session, doc.id, "numero_factura")
    assert found is not None
    assert found.field_name == "numero_factura"


def test_get_field_not_found(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    db_session.commit()

    assert crud.get_field(db_session, doc.id, "campo_inexistente") is None


# ---------------------------------------------------------------------------
# count_uncorrected
# ---------------------------------------------------------------------------

def test_count_uncorrected_returns_correct_count(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    _field(db_session, doc, "campo_a", is_corrected=False)
    _field(db_session, doc, "campo_b", is_corrected=False)
    _field(db_session, doc, "campo_c", is_corrected=True)
    db_session.commit()

    count = crud.count_uncorrected(db_session, doc.id)
    assert count == 2


def test_count_uncorrected_all_corrected(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    _field(db_session, doc, "campo_x", is_corrected=True)
    db_session.commit()

    assert crud.count_uncorrected(db_session, doc.id) == 0


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def test_add_field(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    db_session.commit()

    new_field = ExtractedData(
        document_id=doc.id,
        field_name="nuevo_campo",
        final_value="valor_nuevo",
        is_corrected=True,
        corrected_by_user_id=user.id,
        corrected_at=datetime.utcnow(),
    )
    crud.add(db_session, new_field)
    db_session.commit()

    found = crud.get_field(db_session, doc.id, "nuevo_campo")
    assert found is not None
    assert found.final_value == "valor_nuevo"


# ---------------------------------------------------------------------------
# update_field
# ---------------------------------------------------------------------------

def test_update_field_sets_values(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    field = _field(db_session, doc, "importe_total", is_corrected=False)
    db_session.commit()

    crud.update_field(db_session, field, "1500.00", user.id)
    db_session.commit()

    updated = crud.get_field(db_session, doc.id, "importe_total")
    assert updated.final_value == "1500.00"
    assert updated.is_corrected is True
    assert updated.corrected_by_user_id == user.id
    assert updated.corrected_at is not None
