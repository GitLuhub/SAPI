import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import uuid
from sqlalchemy.orm import Session
from app.db.models.document import Document
from app.db.models.user import User
from app.tasks.document_processing_tasks import process_document_task

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
@patch("app.tasks.document_processing_tasks.ai_service")
def test_process_document_task(mock_ai_service, mock_download_file, db_session: Session):
    # Setup Data
    user = User(
        id=uuid.uuid4(),
        username="taskuser",
        email="task@test.com",
        hashed_password="hash",
        role="user"
    )
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        original_filename="taskdoc.pdf",
        storage_path="path/test.pdf",
        file_size="100",
        mime_type="application/pdf",
        status="UPLOADED",
        upload_user_id=user.id
    )
    db_session.add(user)
    db_session.add(doc)
    db_session.commit()
    
    # Mocking
    mock_download_file.return_value = b"text content"
    mock_ai_service.classify_document.return_value = ("Factura de Proveedor", "0.95")
    mock_ai_service.extract_entities.return_value = [{"field_name": "numero_factura", "ai_extracted_value": "123", "ai_confidence": "0.9"}]
    mock_ai_service.summarize_document.return_value = "Summary"
    
    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = process_document_task(str(doc_id))
    
    assert result["status"] == "success"
    assert result["document_id"] == str(doc_id)
    assert result["confidence"] == "0.95"
    
    db_session.refresh(doc)
    assert doc.status == "PROCESSED"
    assert doc.executive_summary == "Summary"
