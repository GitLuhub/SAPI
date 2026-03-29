"""Tests para endpoints GDPR: export y right-to-erasure."""
import json
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, create_access_token
from app.db.models.document import Document
from app.db.models.extracted_data import ExtractedData
from app.db.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _token(user: User) -> str:
    return create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=30))


def _auth(user: User) -> dict:
    return {"Authorization": f"Bearer {_token(user)}"}


def _json_delete(user: User, password: str) -> dict:
    """Headers para DELETE con body JSON (TestClient no soporta json= en delete)."""
    return {
        "Authorization": f"Bearer {_token(user)}",
        "Content-Type": "application/json",
    }


def _user(db: Session, password: str = "pass123") -> User:
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=f"gdpr_{suffix}",
        email=f"gdpr_{suffix}@test.com",
        hashed_password=get_password_hash(password),
        role="user",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _doc(db: Session, user: User, filename: str = "doc.pdf") -> Document:
    d = Document(
        original_filename=filename,
        storage_path=f"docs/{filename}",
        file_size="1024",
        mime_type="application/pdf",
        status="PROCESSED",
        upload_user_id=user.id,
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def _field(db: Session, doc: Document, field_name: str = "numero_factura") -> ExtractedData:
    ef = ExtractedData(
        document_id=doc.id,
        field_name=field_name,
        field_label=field_name.replace("_", " ").title(),
        ai_extracted_value="F-001",
        final_value="F-001",
        is_corrected=False,
    )
    db.add(ef)
    db.commit()
    db.refresh(ef)
    return ef


# ---------------------------------------------------------------------------
# J1 — GET /users/me/export
# ---------------------------------------------------------------------------

def test_export_returns_user_info(client: TestClient, db_session: Session):
    user = _user(db_session)
    response = client.get("/api/v1/users/me/export", headers=_auth(user))
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == user.username
    assert data["email"] == user.email
    assert "exported_at" in data


def test_export_includes_documents_and_fields(client: TestClient, db_session: Session):
    user = _user(db_session)
    doc = _doc(db_session, user, "factura.pdf")
    _field(db_session, doc, "numero_factura")

    response = client.get("/api/v1/users/me/export", headers=_auth(user))
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["original_filename"] == "factura.pdf"
    assert len(data["documents"][0]["extracted_fields"]) == 1
    assert data["documents"][0]["extracted_fields"][0]["field_name"] == "numero_factura"


def test_export_no_documents(client: TestClient, db_session: Session):
    user = _user(db_session)
    response = client.get("/api/v1/users/me/export", headers=_auth(user))
    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_export_only_own_documents(client: TestClient, db_session: Session):
    user_a = _user(db_session)
    user_b = _user(db_session)
    _doc(db_session, user_b, "other.pdf")

    response = client.get("/api/v1/users/me/export", headers=_auth(user_a))
    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_export_requires_auth(client: TestClient):
    response = client.get("/api/v1/users/me/export")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# J2 — DELETE /users/me
# ---------------------------------------------------------------------------

def _delete_me(client: TestClient, user: User, password: str):
    return client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=_auth(user),
        json={"password": password},
    )


def test_delete_account_correct_password(client: TestClient, db_session: Session):
    user = _user(db_session, password="mypass123")
    user_id = user.id

    response = _delete_me(client, user, "mypass123")
    assert response.status_code == 204

    from app.db.models.user import User as UserModel
    assert db_session.get(UserModel, user_id) is None


def test_delete_account_wrong_password(client: TestClient, db_session: Session):
    user = _user(db_session, password="correctpass")
    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=_auth(user),
        json={"password": "wrongpass"},
    )
    assert response.status_code == 400
    assert "Incorrect password" in response.json()["detail"]


def test_delete_account_removes_documents(client: TestClient, db_session: Session):
    user = _user(db_session, password="pass123")
    doc = _doc(db_session, user, "to_delete.pdf")
    _field(db_session, doc, "campo_test")
    doc_id = doc.id

    response = _delete_me(client, user, "pass123")
    assert response.status_code == 204

    from app.db.models.document import Document as DocModel
    from app.db.models.extracted_data import ExtractedData as EDModel

    assert db_session.get(DocModel, doc_id) is None
    remaining = db_session.query(EDModel).filter(EDModel.document_id == doc_id).count()
    assert remaining == 0


def test_delete_account_requires_auth(client: TestClient):
    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": "pass"},
    )
    assert response.status_code == 401


def test_delete_account_requires_password_field(client: TestClient, db_session: Session):
    user = _user(db_session)
    response = client.request(
        "DELETE",
        "/api/v1/users/me",
        headers=_auth(user),
        json={},
    )
    assert response.status_code == 422


def test_delete_account_storage_error_is_ignored(client: TestClient, db_session: Session):
    """El endpoint no falla si el archivo no existe en storage (best-effort)."""
    from unittest.mock import AsyncMock, patch

    user = _user(db_session, password="pass123")
    _doc(db_session, user, "missing.pdf")

    with patch(
        "app.api.v1.endpoints.users.StorageService.delete_file",
        new_callable=AsyncMock,
        side_effect=FileNotFoundError("not found"),
    ):
        response = _delete_me(client, user, "pass123")

    assert response.status_code == 204
