import uuid
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.db.models.document import Document, DocumentType
from app.db.models.extracted_data import ExtractedData
from app.core.security import get_password_hash, create_access_token
from datetime import timedelta


def create_test_token(user: User) -> str:
    return create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=30))


def setup_user(db_session: Session, username="docuser") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=get_password_hash("password123"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_doc(db_session: Session, user: User, status="UPLOADED", doc_id=None) -> Document:
    doc_id = doc_id or uuid.uuid4()
    doc = Document(
        id=doc_id,
        original_filename="test.pdf",
        storage_path="documents/test.pdf",
        file_size="100",
        mime_type="application/pdf",
        status=status,
        upload_user_id=user.id,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@patch("app.api.v1.endpoints.documents.notification_service")
@patch("app.api.v1.endpoints.documents.StorageService.upload_file", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.documents.MessageBrokerService")
def test_upload_document(mock_broker, mock_upload, mock_notify, client: TestClient, db_session: Session):
    user = setup_user(db_session)
    token = create_test_token(user)
    response = client.post(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")},
    )
    assert response.status_code == 202


@patch("app.api.v1.endpoints.documents.StorageService.upload_file", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.documents.MessageBrokerService")
def test_upload_invalid_extension(mock_broker, mock_upload, client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser2")
    token = create_test_token(user)
    response = client.post(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
    )
    assert response.status_code == 400


@patch("app.api.v1.endpoints.documents.StorageService.upload_file", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.documents.MessageBrokerService")
def test_upload_empty_file(mock_broker, mock_upload, client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser3")
    token = create_test_token(user)
    response = client.post(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 400


def test_upload_unauthenticated(client: TestClient):
    response = client.post(
        "/api/v1/documents/",
        files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

def test_list_documents(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser4")
    token = create_test_token(user)
    response = client.get("/api/v1/documents/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_list_documents_unauthenticated(client: TestClient):
    response = client.get("/api/v1/documents/")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Get document
# ---------------------------------------------------------------------------

def test_get_document(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser5")
    token = create_test_token(user)
    doc = make_doc(db_session, user)
    response = client.get(f"/api/v1/documents/{doc.id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["original_filename"] == "test.pdf"


def test_get_document_not_found(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser6")
    token = create_test_token(user)
    response = client.get(f"/api/v1/documents/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def test_get_document_status(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser7")
    token = create_test_token(user)
    doc = make_doc(db_session, user)
    response = client.get(f"/api/v1/documents/{doc.id}/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "UPLOADED"


# ---------------------------------------------------------------------------
# Data (extracted fields)
# ---------------------------------------------------------------------------

def test_get_document_data(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser8")
    token = create_test_token(user)
    doc = make_doc(db_session, user)
    ed = ExtractedData(document_id=doc.id, field_name="field1", final_value="value1", is_corrected=False)
    db_session.add(ed)
    db_session.commit()
    response = client.get(f"/api/v1/documents/{doc.id}/data", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert len(response.json()["extracted_fields"]) == 1


def test_get_document_data_not_found(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser9")
    token = create_test_token(user)
    response = client.get(f"/api/v1/documents/{uuid.uuid4()}/data", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_update_document_data(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser10")
    token = create_test_token(user)
    doc = make_doc(db_session, user, status="REVIEW_NEEDED")
    ed = ExtractedData(document_id=doc.id, field_name="field1", final_value="old_val", is_corrected=False)
    db_session.add(ed)
    db_session.commit()
    response = client.put(
        f"/api/v1/documents/{doc.id}/data",
        headers={"Authorization": f"Bearer {token}"},
        json={"updates": [{"field_name": "field1", "new_value": "new_val"}]},
    )
    assert response.status_code == 200
    db_session.refresh(ed)
    assert ed.final_value == "new_val"
    assert ed.is_corrected is True


# ---------------------------------------------------------------------------
# Document types
# ---------------------------------------------------------------------------

def test_list_document_types(client: TestClient, db_session: Session):
    user = setup_user(db_session, username="docuser11")
    token = create_test_token(user)
    dt = DocumentType(name="Factura", description="Factura comercial", is_active=True)
    db_session.add(dt)
    db_session.commit()
    response = client.get("/api/v1/documents/types/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    names = [t["name"] for t in response.json()]
    assert "Factura" in names
