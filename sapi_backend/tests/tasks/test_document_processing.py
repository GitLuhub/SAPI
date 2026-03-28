import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.extracted_data import ExtractedData
from app.db.models.user import User
from app.tasks.document_processing_tasks import process_document_task


def _setup(db: Session, doc_id=None, user_id=None):
    user = User(
        id=user_id or uuid.uuid4(),
        username=f"taskuser_{uuid.uuid4().hex[:6]}",
        email=f"task_{uuid.uuid4().hex[:6]}@test.com",
        hashed_password="hash",
        role="user",
    )
    doc = Document(
        id=doc_id or uuid.uuid4(),
        original_filename="taskdoc.pdf",
        storage_path="path/test.pdf",
        file_size="100",
        mime_type="application/pdf",
        status="UPLOADED",
        upload_user_id=user.id,
    )
    db.add(user)
    db.add(doc)
    db.commit()
    return user, doc


# ---------------------------------------------------------------------------
# Success — confidence >= 0.7 → PROCESSED
# ---------------------------------------------------------------------------

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
@patch("app.tasks.document_processing_tasks.ai_service")
def test_process_document_task(mock_ai, mock_download, db_session: Session):
    user, doc = _setup(db_session)
    mock_download.return_value = b"text content"
    mock_ai.classify_document.return_value = ("Factura de Proveedor", "0.95")
    mock_ai.extract_entities.return_value = [
        {"field_name": "numero_factura", "ai_extracted_value": "123", "ai_confidence": "0.9"}
    ]
    mock_ai.summarize_document.return_value = "Summary"

    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = process_document_task(str(doc.id))

    assert result["status"] == "success"
    assert result["document_id"] == str(doc.id)
    assert result["confidence"] == "0.95"
    db_session.refresh(doc)
    assert doc.status == "PROCESSED"
    assert doc.executive_summary == "Summary"


# ---------------------------------------------------------------------------
# Low confidence → REVIEW_NEEDED
# ---------------------------------------------------------------------------

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
@patch("app.tasks.document_processing_tasks.ai_service")
def test_process_document_task_low_confidence(mock_ai, mock_download, db_session: Session):
    user, doc = _setup(db_session)
    mock_download.return_value = b"text content"
    mock_ai.classify_document.return_value = ("Factura de Proveedor", "0.50")
    mock_ai.extract_entities.return_value = []
    mock_ai.summarize_document.return_value = "Low confidence summary"

    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = process_document_task(str(doc.id))

    assert result["status"] == "success"
    db_session.refresh(doc)
    assert doc.status == "REVIEW_NEEDED"


# ---------------------------------------------------------------------------
# Document not found
# ---------------------------------------------------------------------------

def test_process_document_task_not_found(db_session: Session):
    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = process_document_task(str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "not found" in result["message"].lower()


# ---------------------------------------------------------------------------
# Binary file (non-UTF-8) — should handle UnicodeDecodeError gracefully
# ---------------------------------------------------------------------------

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
@patch("app.tasks.document_processing_tasks.ai_service")
def test_process_document_task_binary_content(mock_ai, mock_download, db_session: Session):
    user, doc = _setup(db_session)
    mock_download.return_value = bytes(range(256))  # Non-UTF-8 binary
    mock_ai.classify_document.return_value = ("Factura de Proveedor", "0.80")
    mock_ai.extract_entities.return_value = []
    mock_ai.summarize_document.return_value = "Binary doc summary"

    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = process_document_task(str(doc.id))

    assert result["status"] == "success"
    # text_content should be the "[Binary document content...]" fallback string
    call_args = mock_ai.classify_document.call_args[0][0]
    assert "Binary document" in call_args


# ---------------------------------------------------------------------------
# Confidence non-numeric → REVIEW_NEEDED
# ---------------------------------------------------------------------------

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
@patch("app.tasks.document_processing_tasks.ai_service")
def test_process_document_task_nonnumeric_confidence(mock_ai, mock_download, db_session: Session):
    user, doc = _setup(db_session)
    mock_download.return_value = b"text"
    mock_ai.classify_document.return_value = ("Factura de Proveedor", "high")
    mock_ai.extract_entities.return_value = []
    mock_ai.summarize_document.return_value = "Summary"

    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = process_document_task(str(doc.id))

    db_session.refresh(doc)
    assert doc.status == "REVIEW_NEEDED"


# ---------------------------------------------------------------------------
# PDF extraction via pypdf (lines 48-53)
# ---------------------------------------------------------------------------

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
@patch("app.tasks.document_processing_tasks.ai_service")
def test_process_document_task_pdf_extraction(mock_ai, mock_download, db_session: Session):
    """Binary non-UTF-8 content → pypdf extraction path (lines 48-53)."""
    user, doc = _setup(db_session)
    mock_download.return_value = bytes([0x80, 0x81, 0x82, 0x83])  # invalid UTF-8

    mock_ai.classify_document.return_value = ("Factura de Proveedor", "0.88")
    mock_ai.extract_entities.return_value = []
    mock_ai.summarize_document.return_value = "PDF Summary"

    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""  # empty → triggers line 52
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]

    with patch("pypdf.PdfReader", return_value=mock_reader):
        with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
            db_session.close = MagicMock()
            result = process_document_task(str(doc.id))

    assert result["status"] == "success"
    call_args = mock_ai.classify_document.call_args[0][0]
    assert "PDF sin texto" in call_args


# ---------------------------------------------------------------------------
# Update existing extracted field (lines 81-83)
# ---------------------------------------------------------------------------

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
@patch("app.tasks.document_processing_tasks.ai_service")
def test_process_document_task_updates_existing_field(mock_ai, mock_download, db_session: Session):
    """When an ExtractedData row already exists for a field, it is updated (lines 81-83)."""
    user, doc = _setup(db_session)

    existing_field = ExtractedData(
        document_id=doc.id,
        field_name="numero_factura",
        field_label="Número de Factura",
        ai_extracted_value="OLD-001",
        ai_confidence="0.7",
        final_value="OLD-001",
        is_corrected=False,
    )
    db_session.add(existing_field)
    db_session.commit()

    mock_download.return_value = b"text content"
    mock_ai.classify_document.return_value = ("Factura de Proveedor", "0.92")
    mock_ai.extract_entities.return_value = [
        {
            "field_name": "numero_factura",
            "ai_extracted_value": "NEW-002",
            "ai_confidence": "0.95",
            "final_value": "NEW-002",
        }
    ]
    mock_ai.summarize_document.return_value = "Summary"

    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = process_document_task(str(doc.id))

    assert result["status"] == "success"
    db_session.refresh(existing_field)
    assert existing_field.ai_extracted_value == "NEW-002"
    assert existing_field.ai_confidence == "0.95"


# ---------------------------------------------------------------------------
# Exception handling + retry (lines 129-139)
# ---------------------------------------------------------------------------

@patch("app.tasks.document_processing_tasks.storage_service.download_file", new_callable=AsyncMock)
def test_process_document_task_exception_marks_error(mock_download, db_session: Session):
    """On exception, document status is set to ERROR and retry is raised (lines 129-139)."""
    user, doc = _setup(db_session)
    mock_download.side_effect = Exception("Storage failure")

    with patch("app.tasks.document_processing_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        with pytest.raises(Exception):
            process_document_task(str(doc.id))

    db_session.refresh(doc)
    assert doc.status == "ERROR"
    assert "Storage failure" in doc.processing_error
