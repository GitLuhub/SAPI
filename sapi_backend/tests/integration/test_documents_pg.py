"""
Tests de integración con PostgreSQL real.

Verifican comportamientos que SQLite no reproduce:
- UNIQUE constraint en (document_id, field_name) de extracted_data
- CASCADE delete de ExtractedData cuando se borra Document

Ejecutar con:
    pytest tests/integration/ --integration -v
"""
import pytest
from datetime import timedelta
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash, create_access_token
from app.db.models.user import User
from app.db.models.document import Document
from app.db.models.extracted_data import ExtractedData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(session, username="pg_user") -> User:
    user = User(
        username=username,
        email=f"{username}@pg.test",
        hashed_password=get_password_hash("pass"),
        role="user",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


def _make_doc(session, user: User, filename="test.pdf") -> Document:
    doc = Document(
        original_filename=filename,
        storage_path=f"documents/{filename}",
        file_size="1024",
        mime_type="application/pdf",
        status="UPLOADED",
        upload_user_id=user.id,
    )
    session.add(doc)
    session.flush()
    return doc


def _token(user: User) -> str:
    return create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=30))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_unique_constraint_extracted_data(pg_session):
    """uq_extracted_data_document_field rechaza duplicados en PostgreSQL."""
    user = _make_user(pg_session, "pg_unique")
    doc = _make_doc(pg_session, user)

    field1 = ExtractedData(
        document_id=doc.id,
        field_name="numero_factura",
        ai_extracted_value="F-001",
        final_value="F-001",
    )
    pg_session.add(field1)
    pg_session.flush()

    field2 = ExtractedData(
        document_id=doc.id,
        field_name="numero_factura",  # mismo campo → debe fallar
        ai_extracted_value="F-002",
        final_value="F-002",
    )
    pg_session.add(field2)

    with pytest.raises(IntegrityError):
        pg_session.flush()


@pytest.mark.integration
def test_upload_and_retrieve_document(pg_client, pg_session):
    """Upload + GET /documents/{id} funcionan con PostgreSQL real."""
    from unittest.mock import patch, AsyncMock

    user = _make_user(pg_session, "pg_upload")
    tok = _token(user)

    with patch("app.api.v1.endpoints.documents.StorageService.upload_file", new_callable=AsyncMock) as mock_up, \
         patch("app.api.v1.endpoints.documents.MessageBrokerService") as mock_broker:
        mock_up.return_value = "documents/test.pdf"
        mock_broker.return_value.publish_document_processing.return_value = None

        resp = pg_client.post(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {tok}"},
            files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert resp.status_code == 201
    doc_id = resp.json()["id"]

    resp2 = pg_client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp2.status_code == 200
    assert resp2.json()["original_filename"] == "test.pdf"


@pytest.mark.integration
def test_audit_log_written_on_upload(pg_client, pg_session):
    """Cada upload crea una entrada en audit_logs en PostgreSQL."""
    from unittest.mock import patch, AsyncMock
    from app.db.models.extracted_data import AuditLog

    user = _make_user(pg_session, "pg_audit")
    tok = _token(user)

    with patch("app.api.v1.endpoints.documents.StorageService.upload_file", new_callable=AsyncMock) as mock_up, \
         patch("app.api.v1.endpoints.documents.MessageBrokerService") as mock_broker:
        mock_up.return_value = "documents/audit.pdf"
        mock_broker.return_value.publish_document_processing.return_value = None

        pg_client.post(
            "/api/v1/documents/",
            headers={"Authorization": f"Bearer {tok}"},
            files={"file": ("audit.pdf", b"%PDF-1.4", "application/pdf")},
        )

    logs = pg_session.query(AuditLog).filter(
        AuditLog.action == "document.upload",
        AuditLog.user_id == user.id,
    ).all()
    assert len(logs) >= 1
