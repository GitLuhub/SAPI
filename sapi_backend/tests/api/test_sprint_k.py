"""
Tests para Sprint K:
  K2 — Exportación CSV/XLSX de campos extraídos  (GET /documents/export)
  K3 — Rate limit dinámico por rol               (get_upload_limit)
"""
import uuid
from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash, decode_token_role
from app.core.limiter import get_upload_limit, upload_key_func
from app.db.models.document import Document, DocumentType
from app.db.models.extracted_data import ExtractedData
from app.db.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def token_for(user: User) -> str:
    return create_access_token(subject=str(user.id), role=user.role or "user",
                               expires_delta=timedelta(minutes=30))


def make_user(db: Session, username: str, role: str = "user") -> User:
    u = User(
        username=username,
        email=f"{username}@k.com",
        hashed_password=get_password_hash("pass"),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_doc(db: Session, user: User, status: str = "PROCESSED") -> Document:
    doc = Document(
        original_filename="factura.pdf",
        storage_path=f"documents/factura_{uuid.uuid4()}.pdf",
        file_size="1000",
        mime_type="application/pdf",
        status=status,
        upload_user_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def add_field(db: Session, doc: Document, field_name: str, value: str) -> ExtractedData:
    f = ExtractedData(
        document_id=doc.id,
        field_name=field_name,
        field_label=field_name.replace("_", " ").title(),
        ai_extracted_value=value,
        ai_confidence="0.95",
        final_value=value,
        is_corrected=False,
    )
    db.add(f)
    db.commit()
    return f


# ---------------------------------------------------------------------------
# K2 — GET /documents/export (CSV)
# ---------------------------------------------------------------------------

def test_export_csv_returns_csv_content(client: TestClient, db_session: Session):
    """Export CSV returns a text/csv response with header row."""
    user = make_user(db_session, "export_csv_user")
    doc = make_doc(db_session, user)
    add_field(db_session, doc, "numero_factura", "F-001")

    resp = client.get(
        "/api/v1/documents/export?format=csv",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    content = resp.text
    assert "ID" in content
    assert "Nombre" in content
    assert "F-001" in content


def test_export_csv_no_fields_still_includes_document(client: TestClient, db_session: Session):
    """Documents without extracted fields still appear in the export (one row)."""
    user = make_user(db_session, "export_csv_nofields")
    doc = make_doc(db_session, user)

    resp = client.get(
        "/api/v1/documents/export",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 200
    assert str(doc.id) in resp.text


def test_export_xlsx_returns_xlsx_content(client: TestClient, db_session: Session):
    """Export XLSX returns the correct MIME type for spreadsheets."""
    user = make_user(db_session, "export_xlsx_user")
    make_doc(db_session, user)

    resp = client.get(
        "/api/v1/documents/export?format=xlsx",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]
    # XLSX files start with PK (ZIP magic bytes)
    assert resp.content[:2] == b"PK"


def test_export_invalid_format_returns_422(client: TestClient, db_session: Session):
    """Requesting an unsupported format returns 422."""
    user = make_user(db_session, "export_bad_fmt")
    resp = client.get(
        "/api/v1/documents/export?format=pdf",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 422


def test_export_requires_auth(client: TestClient):
    """Export without a token returns 401."""
    resp = client.get("/api/v1/documents/export")
    assert resp.status_code == 401


def test_export_csv_status_filter(client: TestClient, db_session: Session):
    """Export with status=PROCESSED excludes ERROR documents from the CSV."""
    user = make_user(db_session, "export_status_filter")
    doc_ok = make_doc(db_session, user, status="PROCESSED")
    doc_err = make_doc(db_session, user, status="ERROR")
    add_field(db_session, doc_ok, "numero_factura", "F-OK")
    add_field(db_session, doc_err, "numero_factura", "F-ERR")

    resp = client.get(
        "/api/v1/documents/export?format=csv&status=PROCESSED",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 200
    assert "F-OK" in resp.text
    assert "F-ERR" not in resp.text


# ---------------------------------------------------------------------------
# K3 — Rate limit dinámico por rol (get_upload_limit + upload_key_func)
# ---------------------------------------------------------------------------

def _make_request_with_token(token: str):
    """Builds a minimal mock Request with an Authorization header."""
    req = MagicMock()
    req.headers = {"Authorization": f"Bearer {token}"}
    req.META = {}
    req.scope = {"type": "http", "client": ("127.0.0.1", 12345)}
    return req


def test_rate_limit_user_gets_10_per_minute():
    """Regular users get 10/minute upload limit."""
    assert get_upload_limit("user:127.0.0.1") == "10/minute"


def test_rate_limit_reviewer_gets_30_per_minute():
    """Document reviewers get 30/minute upload limit."""
    assert get_upload_limit("document_reviewer:127.0.0.1") == "30/minute"


def test_rate_limit_admin_gets_1000_per_minute():
    """Admins get 1000/minute upload limit (effectively unlimited)."""
    assert get_upload_limit("admin:127.0.0.1") == "1000/minute"


def test_rate_limit_unknown_role_gets_default():
    """Unknown role prefix defaults to 10/minute."""
    assert get_upload_limit("unknown:127.0.0.1") == "10/minute"


def test_upload_key_func_user_role():
    """upload_key_func returns 'user:{ip}' for a regular user token."""
    token = create_access_token(subject=str(uuid.uuid4()), role="user",
                                expires_delta=timedelta(minutes=5))
    req = MagicMock()
    req.headers = {"Authorization": f"Bearer {token}"}
    req.scope = {"type": "http", "client": ("192.168.1.1", 9000)}
    key = upload_key_func(req)
    assert key.startswith("user:")


def test_upload_key_func_admin_role():
    """upload_key_func returns 'admin:{ip}' for an admin token."""
    token = create_access_token(subject=str(uuid.uuid4()), role="admin",
                                expires_delta=timedelta(minutes=5))
    req = MagicMock()
    req.headers = {"Authorization": f"Bearer {token}"}
    req.scope = {"type": "http", "client": ("192.168.1.1", 9000)}
    key = upload_key_func(req)
    assert key.startswith("admin:")


def test_upload_key_func_no_token():
    """upload_key_func defaults to 'user:{ip}' when no Authorization header."""
    req = MagicMock()
    req.headers = {}
    req.scope = {"type": "http", "client": ("10.0.0.1", 80)}
    key = upload_key_func(req)
    assert key.startswith("user:")


# ---------------------------------------------------------------------------
# K3 — decode_token_role
# ---------------------------------------------------------------------------

def test_decode_token_role_returns_correct_role():
    """decode_token_role extracts the role claim from a valid JWT."""
    for role in ("user", "document_reviewer", "admin"):
        token = create_access_token(subject=str(uuid.uuid4()), role=role,
                                    expires_delta=timedelta(minutes=5))
        assert decode_token_role(token) == role


def test_decode_token_role_defaults_to_user_for_bad_token():
    """decode_token_role returns 'user' for invalid tokens."""
    assert decode_token_role("garbage.token.here") == "user"
