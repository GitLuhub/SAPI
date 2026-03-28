"""
Additional document endpoint tests covering:
- list with filters (status, search_query, document_type_id, pagination)
- download / preview
- update_document_data creating a new field
- get_document_status for all statuses
- upload file too large
"""
import uuid
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.db.models.document import Document, DocumentType
from app.db.models.extracted_data import ExtractedData
from app.db.models.user import User
from datetime import timedelta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def token_for(user: User) -> str:
    return create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=30))


def make_user(db: Session, username: str) -> User:
    u = User(
        username=username,
        email=f"{username}@extra.com",
        hashed_password=get_password_hash("pass"),
        role="user",
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_doc(db: Session, user: User, status="UPLOADED", filename="file.pdf") -> Document:
    doc = Document(
        original_filename=filename,
        storage_path=f"documents/{filename}",
        file_size="500",
        mime_type="application/pdf",
        status=status,
        upload_user_id=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ---------------------------------------------------------------------------
# List with filters
# ---------------------------------------------------------------------------

def test_list_documents_filter_by_status(client: TestClient, db_session: Session):
    user = make_user(db_session, "filter_status")
    tok = token_for(user)
    make_doc(db_session, user, status="PROCESSED", filename="proc.pdf")
    make_doc(db_session, user, status="ERROR", filename="err.pdf")

    resp = client.get(
        "/api/v1/documents/?status=PROCESSED",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(i["status"] == "PROCESSED" for i in items)


def test_list_documents_filter_by_search(client: TestClient, db_session: Session):
    user = make_user(db_session, "filter_search")
    tok = token_for(user)
    make_doc(db_session, user, filename="unique_contract_xyz.pdf")
    make_doc(db_session, user, filename="another_file.pdf")

    resp = client.get(
        "/api/v1/documents/?search_query=unique_contract",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert "unique_contract" in items[0]["original_filename"]


def test_list_documents_pagination(client: TestClient, db_session: Session):
    user = make_user(db_session, "pag_user")
    tok = token_for(user)
    for i in range(5):
        make_doc(db_session, user, filename=f"pag_{i}.pdf")

    resp = client.get(
        "/api/v1/documents/?page=1&size=2",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["size"] == 2


def test_list_documents_filter_by_document_type(client: TestClient, db_session: Session):
    user = make_user(db_session, "filter_type")
    tok = token_for(user)
    dt = DocumentType(name="Contrato Extra", is_active=True)
    db_session.add(dt)
    db_session.commit()
    db_session.refresh(dt)

    doc = make_doc(db_session, user, filename="typed.pdf")
    doc.document_type_id = dt.id
    db_session.commit()

    resp = client.get(
        f"/api/v1/documents/?document_type_id={dt.id}",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

@patch("app.api.v1.endpoints.documents.StorageService.download_file", new_callable=AsyncMock)
def test_download_document(mock_download, client: TestClient, db_session: Session):
    mock_download.return_value = b"%PDF-1.4 content"
    user = make_user(db_session, "download_user")
    tok = token_for(user)
    doc = make_doc(db_session, user)

    resp = client.get(
        f"/api/v1/documents/{doc.id}/download",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    assert b"%PDF" in resp.content
    assert "attachment" in resp.headers["content-disposition"]


@patch("app.api.v1.endpoints.documents.StorageService.download_file", new_callable=AsyncMock)
def test_download_document_not_found(mock_download, client: TestClient, db_session: Session):
    user = make_user(db_session, "download_nf")
    tok = token_for(user)
    resp = client.get(
        f"/api/v1/documents/{uuid.uuid4()}/download",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

@patch("app.api.v1.endpoints.documents.StorageService.download_file", new_callable=AsyncMock)
def test_preview_document(mock_download, client: TestClient, db_session: Session):
    mock_download.return_value = b"%PDF-1.4 inline content"
    user = make_user(db_session, "preview_user")
    tok = token_for(user)
    doc = make_doc(db_session, user)

    resp = client.get(
        f"/api/v1/documents/{doc.id}/preview",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    assert "inline" in resp.headers["content-disposition"]


@patch("app.api.v1.endpoints.documents.StorageService.download_file", new_callable=AsyncMock)
def test_preview_document_not_found(mock_download, client: TestClient, db_session: Session):
    user = make_user(db_session, "preview_nf")
    tok = token_for(user)
    resp = client.get(
        f"/api/v1/documents/{uuid.uuid4()}/preview",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update data — creates new field when it doesn't exist
# ---------------------------------------------------------------------------

def test_update_document_data_creates_new_field(client: TestClient, db_session: Session):
    user = make_user(db_session, "update_new_field")
    tok = token_for(user)
    doc = make_doc(db_session, user, status="REVIEW_NEEDED")

    resp = client.put(
        f"/api/v1/documents/{doc.id}/data",
        headers={"Authorization": f"Bearer {tok}"},
        json={"updates": [{"field_name": "brand_new_field", "new_value": "created_value"}]},
    )
    assert resp.status_code == 200

    field = db_session.query(ExtractedData).filter(
        ExtractedData.document_id == doc.id,
        ExtractedData.field_name == "brand_new_field",
    ).first()
    assert field is not None
    assert field.final_value == "created_value"
    assert field.is_corrected is True


def test_update_document_data_doc_not_found(client: TestClient, db_session: Session):
    user = make_user(db_session, "update_nf")
    tok = token_for(user)
    resp = client.put(
        f"/api/v1/documents/{uuid.uuid4()}/data",
        headers={"Authorization": f"Bearer {tok}"},
        json={"updates": [{"field_name": "f", "new_value": "v"}]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# get_document_status for all statuses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_val, expected_fragment", [
    ("UPLOADED",  "waiting"),
    ("PROCESSING", "being processed"),
    ("PROCESSED", "successfully"),
    ("REVIEW_NEEDED", "review"),
    ("ERROR", "error"),
])
def test_get_document_status_messages(
    client: TestClient, db_session: Session, status_val: str, expected_fragment: str
):
    user = make_user(db_session, f"status_{status_val.lower()}")
    tok = token_for(user)
    doc = make_doc(db_session, user, status=status_val)

    resp = client.get(
        f"/api/v1/documents/{doc.id}/status",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert resp.status_code == 200
    assert expected_fragment in resp.json()["message"].lower()


# ---------------------------------------------------------------------------
# Upload — file too large
# ---------------------------------------------------------------------------

@patch("app.api.v1.endpoints.documents.StorageService.upload_file", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.documents.MessageBrokerService")
def test_upload_file_too_large(mock_broker, mock_upload, client: TestClient, db_session: Session):
    user = make_user(db_session, "large_file")
    tok = token_for(user)
    big_content = b"a" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte

    resp = client.post(
        "/api/v1/documents/",
        headers={"Authorization": f"Bearer {tok}"},
        files={"file": ("big.pdf", big_content, "application/pdf")},
    )
    assert resp.status_code == 400
    assert "large" in resp.json()["detail"].lower()
