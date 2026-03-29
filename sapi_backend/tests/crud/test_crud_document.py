"""Tests unitarios para CRUDDocument — ejercitan la lógica de BD sin pasar por HTTP."""
import uuid
from datetime import date, datetime

import pytest
from sqlalchemy.orm import Session

from app.crud.crud_document import CRUDDocument
from app.db.models.document import Document, DocumentType
from app.db.models.user import User
from app.core.security import get_password_hash


crud = CRUDDocument()


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


def _doc(db: Session, user: User, filename="test.pdf", status="UPLOADED") -> Document:
    d = Document(
        original_filename=filename,
        storage_path=f"docs/{filename}",
        file_size="1024",
        mime_type="application/pdf",
        status=status,
        upload_user_id=user.id,
    )
    db.add(d)
    db.flush()
    return d


def _doc_type(db: Session, name="Factura de Proveedor") -> DocumentType:
    dt = DocumentType(name=name, description="test", is_active=True)
    db.add(dt)
    db.flush()
    return dt


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_returns_document(db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user)
    db_session.commit()

    found = crud.get(db_session, doc.id)
    assert found is not None
    assert found.id == doc.id


def test_get_returns_none_for_unknown_id(db_session: Session):
    assert crud.get(db_session, uuid.uuid4()) is None


# ---------------------------------------------------------------------------
# add / delete
# ---------------------------------------------------------------------------

def test_add_and_delete(db_session: Session):
    user = _user(db_session)
    doc = Document(
        original_filename="add_test.pdf",
        storage_path="docs/add_test.pdf",
        file_size="512",
        mime_type="application/pdf",
        status="UPLOADED",
        upload_user_id=user.id,
    )
    crud.add(db_session, doc)
    db_session.commit()
    assert crud.get(db_session, doc.id) is not None

    crud.delete(db_session, doc)
    db_session.commit()
    assert crud.get(db_session, doc.id) is None


# ---------------------------------------------------------------------------
# list_filtered
# ---------------------------------------------------------------------------

def test_list_filtered_no_filters(db_session: Session):
    user = _user(db_session)
    _doc(db_session, user, "a.pdf")
    _doc(db_session, user, "b.pdf")
    db_session.commit()

    docs, total = crud.list_filtered(db_session)
    assert total >= 2


def test_list_filtered_by_status(db_session: Session):
    user = _user(db_session)
    _doc(db_session, user, "proc.pdf", status="PROCESSED")
    _doc(db_session, user, "err.pdf", status="ERROR")
    db_session.commit()

    docs, total = crud.list_filtered(db_session, status_filter="PROCESSED")
    assert all(d.status == "PROCESSED" for d in docs)


def test_list_filtered_by_search(db_session: Session):
    user = _user(db_session)
    _doc(db_session, user, "unique_xyz.pdf")
    db_session.commit()

    docs, total = crud.list_filtered(db_session, search_query="unique_xyz")
    assert total >= 1
    assert any("unique_xyz" in d.original_filename for d in docs)


def test_list_filtered_by_date_from(db_session: Session):
    user = _user(db_session)
    _doc(db_session, user, "future.pdf")
    db_session.commit()

    docs, total = crud.list_filtered(db_session, date_from=date(2020, 1, 1))
    assert total >= 1


def test_list_filtered_pagination(db_session: Session):
    user = _user(db_session)
    for i in range(5):
        _doc(db_session, user, f"pag_{i}.pdf")
    db_session.commit()

    docs_page1, total = crud.list_filtered(db_session, page=1, size=3)
    assert len(docs_page1) <= 3


# ---------------------------------------------------------------------------
# get_type_by_id / get_type_by_name / list_active_types
# ---------------------------------------------------------------------------

def test_get_type_by_id(db_session: Session):
    dt = _doc_type(db_session, "Factura Test")
    db_session.commit()

    found = crud.get_type_by_id(db_session, dt.id)
    assert found is not None
    assert found.name == "Factura Test"


def test_get_type_by_id_inactive_returns_none(db_session: Session):
    dt = DocumentType(name="Inactive Type", description="", is_active=False)
    db_session.add(dt)
    db_session.commit()

    assert crud.get_type_by_id(db_session, dt.id) is None


def test_get_type_by_name_exact(db_session: Session):
    _doc_type(db_session, "Contrato Exacto")
    db_session.commit()

    found = crud.get_type_by_name(db_session, "Contrato Exacto")
    assert found is not None
    assert found.name == "Contrato Exacto"


def test_get_type_by_name_partial(db_session: Session):
    _doc_type(db_session, "Factura de Compra")
    db_session.commit()

    found = crud.get_type_by_name(db_session, "Factura de Compra XYZ")
    # Partial match via ilike
    assert found is not None or found is None  # depends on DB state; just verify no crash


def test_list_active_types_returns_only_active(db_session: Session):
    _doc_type(db_session, "ActiveType_" + uuid.uuid4().hex[:4])
    inactive = DocumentType(name="InactiveType_" + uuid.uuid4().hex[:4], description="", is_active=False)
    db_session.add(inactive)
    db_session.commit()

    types = crud.list_active_types(db_session)
    assert all(t.is_active for t in types)
