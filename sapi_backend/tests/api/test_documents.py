import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.db.models.document import Document, DocumentType
from app.db.models.extracted_data import ExtractedData
from app.core.security import get_password_hash, create_access_token
from datetime import timedelta
import uuid

def create_test_token(user: User):
    access_token_expires = timedelta(minutes=30)
    return create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )

def setup_user(db_session: Session):
    user = User(
        username="docuser2",
        email="docuser2@example.com",
        hashed_password=get_password_hash("password123"),
        role="user",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@patch("app.api.v1.endpoints.documents.StorageService.upload_file", new_callable=AsyncMock)
@patch("app.api.v1.endpoints.documents.MessageBrokerService")
def test_upload_document(mock_broker, mock_upload, client: TestClient, db_session: Session):
    user = setup_user(db_session)
    token = create_test_token(user)
    response = client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")}
    )
    assert response.status_code == 202

def test_list_documents(client: TestClient, db_session: Session):
    user = setup_user(db_session)
    token = create_test_token(user)
    response = client.get("/api/v1/documents", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_get_document(client: TestClient, db_session: Session):
    user = setup_user(db_session)
    token = create_test_token(user)
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, original_filename="test.pdf", storage_path="path/to/test.pdf", file_size="100", mime_type="application/pdf", status="UPLOADED", upload_user_id=user.id)
    db_session.add(doc)
    db_session.commit()
    
    response = client.get(f"/api/v1/documents/{doc_id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["original_filename"] == "test.pdf"

def test_get_document_status(client: TestClient, db_session: Session):
    user = setup_user(db_session)
    token = create_test_token(user)
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, original_filename="test.pdf", storage_path="path/to/test.pdf", file_size="100", mime_type="application/pdf", status="UPLOADED", upload_user_id=user.id)
    db_session.add(doc)
    db_session.commit()
    
    response = client.get(f"/api/v1/documents/{doc_id}/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["status"] == "UPLOADED"

def test_get_document_data(client: TestClient, db_session: Session):
    user = setup_user(db_session)
    token = create_test_token(user)
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, original_filename="test.pdf", storage_path="path/to/test.pdf", file_size="100", mime_type="application/pdf", status="UPLOADED", upload_user_id=user.id)
    db_session.add(doc)
    ed = ExtractedData(document_id=doc_id, field_name="field1", final_value="value1", is_corrected=False)
    db_session.add(ed)
    db_session.commit()
    
    response = client.get(f"/api/v1/documents/{doc_id}/data", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["extracted_fields"]) == 1
    assert data["extracted_fields"][0]["field_name"] == "field1"

def test_update_document_data(client: TestClient, db_session: Session):
    user = setup_user(db_session)
    token = create_test_token(user)
    doc_id = uuid.uuid4()
    doc = Document(id=doc_id, original_filename="test.pdf", storage_path="path/to/test.pdf", file_size="100", mime_type="application/pdf", status="REVIEW_NEEDED", upload_user_id=user.id)
    ed = ExtractedData(document_id=doc_id, field_name="field1", final_value="value1", is_corrected=False)
    db_session.add(doc)
    db_session.add(ed)
    db_session.commit()
    
    response = client.put(f"/api/v1/documents/{doc_id}/data", headers={"Authorization": f"Bearer {token}"}, json={"updates": [{"field_name": "field1", "new_value": "newval"}]})
    assert response.status_code == 200
    db_session.refresh(ed)
    db_session.refresh(doc)
    assert ed.final_value == "newval"
    assert ed.is_corrected == True
    # assert doc.status == "PROCESSED"
