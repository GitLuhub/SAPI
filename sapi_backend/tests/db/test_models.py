"""Tests for model __repr__ methods."""
import uuid
from app.db.models.document import DocumentType, Document
from app.db.models.extracted_data import ExtractedData, AuditLog
from app.db.models.user import User


def test_document_type_repr():
    dt = DocumentType(name="Factura de Proveedor")
    dt.id = uuid.uuid4()
    result = repr(dt)
    assert "Factura de Proveedor" in result
    assert "DocumentType" in result


def test_document_repr():
    doc = Document(
        original_filename="invoice.pdf",
        storage_path="docs/invoice.pdf",
        upload_user_id=uuid.uuid4(),
    )
    doc.id = uuid.uuid4()
    doc.status = "PROCESSED"
    result = repr(doc)
    assert "invoice.pdf" in result
    assert "PROCESSED" in result
    assert "Document" in result


def test_extracted_data_repr():
    doc_id = uuid.uuid4()
    ed = ExtractedData(
        document_id=doc_id,
        field_name="numero_factura",
        final_value="INV-001",
    )
    ed.id = uuid.uuid4()
    result = repr(ed)
    assert "numero_factura" in result
    assert "ExtractedData" in result


def test_audit_log_repr():
    log = AuditLog(action="upload")
    log.id = uuid.uuid4()
    log.user_id = uuid.uuid4()
    result = repr(log)
    assert "upload" in result
    assert "AuditLog" in result


def test_user_repr():
    user = User(
        username="testuser",
        email="test@example.com",
        hashed_password="hashed",
        role="admin",
    )
    user.id = uuid.uuid4()
    result = repr(user)
    assert "testuser" in result
    assert "admin" in result
    assert "User" in result
