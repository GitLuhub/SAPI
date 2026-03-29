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
    user = make_user_with_role(db_session, "update_new_field", "document_reviewer")
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


# ---------------------------------------------------------------------------
# Authorization — Sprint B
# ---------------------------------------------------------------------------

def make_user_with_role(db: Session, username: str, role: str) -> User:
    u = User(
        username=username,
        email=f"{username}@auth.com",
        hashed_password=get_password_hash("pass"),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_other_user_cannot_access_document(client: TestClient, db_session: Session):
    """A plain user cannot read another user's document — expects 403."""
    owner = make_user(db_session, "owner_b1")
    other = make_user(db_session, "other_b1")
    doc = make_doc(db_session, owner)

    resp = client.get(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token_for(other)}"},
    )
    assert resp.status_code == 403


def test_reviewer_can_access_any_document(client: TestClient, db_session: Session):
    """A document_reviewer can read documents uploaded by other users."""
    owner = make_user(db_session, "owner_b2")
    reviewer = make_user_with_role(db_session, "reviewer_b2", "document_reviewer")
    doc = make_doc(db_session, owner)

    resp = client.get(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token_for(reviewer)}"},
    )
    assert resp.status_code == 200


def test_admin_can_access_any_document(client: TestClient, db_session: Session):
    """An admin can read documents uploaded by other users."""
    owner = make_user(db_session, "owner_b3")
    admin = make_user_with_role(db_session, "admin_b3", "admin")
    doc = make_doc(db_session, owner)

    resp = client.get(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token_for(admin)}"},
    )
    assert resp.status_code == 200


def test_plain_user_cannot_update_document_data(client: TestClient, db_session: Session):
    """A plain user (role=user) cannot correct extracted fields — expects 403."""
    owner = make_user(db_session, "owner_b4")
    plain = make_user(db_session, "plain_b4")
    doc = make_doc(db_session, owner, status="REVIEW_NEEDED")

    payload = {"updates": [{"field_name": "numero_factura", "new_value": "X-001"}]}
    resp = client.put(
        f"/api/v1/documents/{doc.id}/data",
        json=payload,
        headers={"Authorization": f"Bearer {token_for(plain)}"},
    )
    assert resp.status_code == 403


def test_reviewer_can_update_document_data(client: TestClient, db_session: Session):
    """A document_reviewer can correct extracted fields on any document."""
    owner = make_user(db_session, "owner_b5")
    reviewer = make_user_with_role(db_session, "reviewer_b5", "document_reviewer")
    doc = make_doc(db_session, owner, status="REVIEW_NEEDED")

    payload = {"updates": [{"field_name": "numero_factura", "new_value": "F-999"}]}
    resp = client.put(
        f"/api/v1/documents/{doc.id}/data",
        json=payload,
        headers={"Authorization": f"Bearer {token_for(reviewer)}"},
    )
    assert resp.status_code == 200


def test_owner_cannot_update_own_document_data(client: TestClient, db_session: Session):
    """The document owner (role=user) also cannot correct fields — that requires reviewer/admin."""
    owner = make_user(db_session, "owner_b6")
    doc = make_doc(db_session, owner, status="REVIEW_NEEDED")

    payload = {"updates": [{"field_name": "numero_factura", "new_value": "F-000"}]}
    resp = client.put(
        f"/api/v1/documents/{doc.id}/data",
        json=payload,
        headers={"Authorization": f"Bearer {token_for(owner)}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /documents/{id} — Sprint D1
# ---------------------------------------------------------------------------

@patch("app.api.v1.endpoints.documents.StorageService.delete_file", new_callable=AsyncMock)
def test_delete_document_owner(mock_delete, client: TestClient, db_session: Session):
    """Document owner can delete their own document (204)."""
    owner = make_user(db_session, "del_owner")
    doc = make_doc(db_session, owner)
    mock_delete.return_value = None

    resp = client.delete(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token_for(owner)}"},
    )
    assert resp.status_code == 204


@patch("app.api.v1.endpoints.documents.StorageService.delete_file", new_callable=AsyncMock)
def test_delete_document_other_user_forbidden(mock_delete, client: TestClient, db_session: Session):
    """A different plain user cannot delete someone else's document (403)."""
    owner = make_user(db_session, "del_owner2")
    other = make_user(db_session, "del_other2")
    doc = make_doc(db_session, owner)

    resp = client.delete(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token_for(other)}"},
    )
    assert resp.status_code == 403


def test_delete_document_not_found(client: TestClient, db_session: Session):
    """Deleting a non-existent document returns 404."""
    owner = make_user(db_session, "del_nf")
    resp = client.delete(
        f"/api/v1/documents/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token_for(owner)}"},
    )
    assert resp.status_code == 404


@patch("app.api.v1.endpoints.documents.StorageService.delete_file", new_callable=AsyncMock)
def test_delete_document_storage_error_still_deletes_from_db(mock_delete, client: TestClient, db_session: Session):
    """If storage deletion fails, document is still removed from the DB."""
    owner = make_user(db_session, "del_storage_err")
    doc = make_doc(db_session, owner)
    mock_delete.side_effect = Exception("Storage unavailable")

    resp = client.delete(
        f"/api/v1/documents/{doc.id}",
        headers={"Authorization": f"Bearer {token_for(owner)}"},
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Date filters in GET /documents/ — Sprint D3
# ---------------------------------------------------------------------------

def test_list_documents_date_from_filter(client: TestClient, db_session: Session):
    """date_from filter excludes documents created before that date."""
    user = make_user(db_session, "date_from_user")
    make_doc(db_session, user, filename="old.pdf")

    resp = client.get(
        "/api/v1/documents/?date_from=2099-01-01",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_documents_date_to_filter(client: TestClient, db_session: Session):
    """date_to filter excludes documents created after that date."""
    user = make_user(db_session, "date_to_user")
    make_doc(db_session, user, filename="recent.pdf")

    resp = client.get(
        "/api/v1/documents/?date_to=2000-01-01",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# POST /documents/{id}/reprocess — Sprint K1
# ---------------------------------------------------------------------------

@patch("app.api.v1.endpoints.documents.MessageBrokerService")
def test_reprocess_error_document(mock_broker, client: TestClient, db_session: Session):
    """Owner can reprocess a document in ERROR status; status resets to UPLOADED."""
    owner = make_user(db_session, "reprocess_owner_error")
    doc = make_doc(db_session, owner, status="ERROR")

    resp = client.post(
        f"/api/v1/documents/{doc.id}/reprocess",
        headers={"Authorization": f"Bearer {token_for(owner)}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UPLOADED"
    assert "requeued" in data["message"].lower()
    db_session.refresh(doc)
    assert doc.status == "UPLOADED"
    assert doc.processing_error is None


@patch("app.api.v1.endpoints.documents.MessageBrokerService")
def test_reprocess_review_needed_document(mock_broker, client: TestClient, db_session: Session):
    """Reviewer can reprocess a REVIEW_NEEDED document."""
    owner = make_user(db_session, "reprocess_owner_rv")
    reviewer = make_user_with_role(db_session, "reprocess_rv", "document_reviewer")
    doc = make_doc(db_session, owner, status="REVIEW_NEEDED")

    resp = client.post(
        f"/api/v1/documents/{doc.id}/reprocess",
        headers={"Authorization": f"Bearer {token_for(reviewer)}"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "UPLOADED"


def test_reprocess_invalid_status_returns_400(client: TestClient, db_session: Session):
    """Reprocessing a PROCESSED document returns 400."""
    owner = make_user(db_session, "reprocess_processed")
    doc = make_doc(db_session, owner, status="PROCESSED")

    resp = client.post(
        f"/api/v1/documents/{doc.id}/reprocess",
        headers={"Authorization": f"Bearer {token_for(owner)}"},
    )
    assert resp.status_code == 400
    assert "cannot reprocess" in resp.json()["detail"].lower()


def test_reprocess_not_found_returns_404(client: TestClient, db_session: Session):
    """Reprocessing a non-existent document returns 404."""
    user = make_user(db_session, "reprocess_nf")
    resp = client.post(
        f"/api/v1/documents/{uuid.uuid4()}/reprocess",
        headers={"Authorization": f"Bearer {token_for(user)}"},
    )
    assert resp.status_code == 404


def test_reprocess_other_user_forbidden(client: TestClient, db_session: Session):
    """A different plain user cannot reprocess someone else's document (403)."""
    owner = make_user(db_session, "reprocess_own")
    other = make_user(db_session, "reprocess_other")
    doc = make_doc(db_session, owner, status="ERROR")

    resp = client.post(
        f"/api/v1/documents/{doc.id}/reprocess",
        headers={"Authorization": f"Bearer {token_for(other)}"},
    )
    assert resp.status_code == 403
