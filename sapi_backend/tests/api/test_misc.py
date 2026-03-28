"""Miscellaneous endpoint and dependency tests."""
import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models.document import Document, DocumentType
from app.db.models.user import User
from app.api.v1.endpoints.documents import validate_file


# ---------------------------------------------------------------------------
# Health check (main.py line 33)
# ---------------------------------------------------------------------------

def test_health_check(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


# ---------------------------------------------------------------------------
# validate_file — no filename (documents.py line 35)
# ---------------------------------------------------------------------------

def test_validate_file_empty_filename():
    mock_file = MagicMock()
    mock_file.filename = ""
    with pytest.raises(HTTPException) as exc_info:
        validate_file(mock_file)
    assert exc_info.value.status_code == 400
    assert "filename" in exc_info.value.detail.lower()


def test_validate_file_none_filename():
    mock_file = MagicMock()
    mock_file.filename = None
    with pytest.raises(HTTPException) as exc_info:
        validate_file(mock_file)
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# deps.get_current_user edge cases (lines 35, 39-40, 44, 47)
# ---------------------------------------------------------------------------

def test_get_current_user_invalid_token(client: TestClient):
    """decode_access_token returns None → 401 (line 35)."""
    resp = client.get(
        "/api/v1/documents/",
        headers={"Authorization": "Bearer this.is.invalid"},
    )
    assert resp.status_code == 401


def test_get_current_user_non_uuid_subject(client: TestClient):
    """Token subject is not a valid UUID → ValueError → 401 (lines 39-40)."""
    token = create_access_token(subject="not-a-uuid", expires_delta=timedelta(minutes=5))
    resp = client.get(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


def test_get_current_user_not_in_db(client: TestClient):
    """Valid UUID token but user does not exist → 401 (line 44)."""
    token = create_access_token(subject=str(uuid.uuid4()), expires_delta=timedelta(minutes=5))
    resp = client.get(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 401


def test_get_current_user_inactive(client: TestClient, db_session: Session):
    """Inactive user → 400 (line 47)."""
    user = User(
        username="inactive_user",
        email="inactive@test.com",
        hashed_password=get_password_hash("pass"),
        role="user",
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=5))
    resp = client.get(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# deps.get_current_active_user with inactive user (line 59)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_current_active_user_inactive_direct():
    """Call get_current_active_user directly with an inactive user (line 59)."""
    from app.api.v1.deps import get_current_active_user

    mock_user = MagicMock()
    mock_user.is_active = False

    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(current_user=mock_user)
    assert exc_info.value.status_code == 400
    assert "inactive" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# documents.get_document_status — not found (line 187)
# ---------------------------------------------------------------------------

def test_get_document_status_not_found(client: TestClient, db_session: Session):
    user = User(
        username="status_nf_user",
        email="status_nf@test.com",
        hashed_password=get_password_hash("pass"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=5))
    resp = client.get(
        f"/api/v1/documents/{uuid.uuid4()}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# documents.get_document_data — with document type (lines 222, 244)
# ---------------------------------------------------------------------------

def test_get_document_data_with_type(client: TestClient, db_session: Session):
    """Document with a document_type_id set covers lines 222 and 244."""
    user = User(
        username="data_type_user",
        email="data_type@test.com",
        hashed_password=get_password_hash("pass"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doc_type = DocumentType(name="Factura Test Type", is_active=True)
    db_session.add(doc_type)
    db_session.commit()
    db_session.refresh(doc_type)

    doc = Document(
        original_filename="typed_doc.pdf",
        storage_path="documents/typed_doc.pdf",
        file_size="500",
        mime_type="application/pdf",
        status="PROCESSED",
        upload_user_id=user.id,
        document_type_id=doc_type.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    token = create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=5))
    resp = client.get(
        f"/api/v1/documents/{doc.id}/data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_type"] is not None
    assert data["document_type"]["name"] == "Factura Test Type"
