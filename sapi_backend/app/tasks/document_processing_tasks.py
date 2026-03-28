import logging
from datetime import datetime
from typing import List
from uuid import UUID

from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models.document import Document, DocumentType
from app.db.models.extracted_data import ExtractedData
from app.services.ai_service import ai_service
from app.services.storage_service import storage_service
from app.services.notification_service import notification_service
from app.db.models.user import User


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_document_task(self, document_id: str) -> dict:
    db: Session = SessionLocal()
    
    try:
        document = db.query(Document).filter(Document.id == UUID(document_id)).first()
        
        if not document:
            logger.error(f"Document not found: {document_id}")
            return {"status": "error", "message": "Document not found"}
        
        document.status = "PROCESSING"
        document.processing_started_at = datetime.utcnow()
        db.commit()
        
        # We need to run the async download in a sync way
        import asyncio
        file_content = asyncio.run(storage_service.download_file(document.storage_path))
        
        if isinstance(file_content, bytes):
            try:
                text_content = file_content.decode('utf-8')
            except UnicodeDecodeError:
                # Intenta extraer texto de PDF con pypdf
                try:
                    import io
                    import pypdf
                    reader = pypdf.PdfReader(io.BytesIO(file_content))
                    pages_text = [page.extract_text() or "" for page in reader.pages]
                    text_content = "\n".join(pages_text).strip()
                    if not text_content:
                        text_content = f"[PDF sin texto extraíble - {len(file_content)} bytes]"
                    logger.info(f"PDF text extracted: {len(text_content)} chars from {len(reader.pages)} pages")
                except Exception as pdf_err:
                    logger.warning(f"PDF extraction failed: {pdf_err}")
                    text_content = f"[Binary document content - {len(file_content)} bytes]"
        
        doc_type, classification_confidence = ai_service.classify_document(text_content)
        
        doc_type_record = db.query(DocumentType).filter(
            DocumentType.name == doc_type
        ).first()
        
        if not doc_type_record:
            doc_type_record = db.query(DocumentType).filter(
                DocumentType.name.ilike(f"%{doc_type}%")
            ).first()
        
        document.document_type_id = doc_type_record.id if doc_type_record else None
        document.classification_confidence = classification_confidence
        
        extracted_fields = ai_service.extract_entities(text_content, doc_type)
        
        for field_data in extracted_fields:
            existing_field = db.query(ExtractedData).filter(
                ExtractedData.document_id == document.id,
                ExtractedData.field_name == field_data["field_name"]
            ).first()
            
            if existing_field:
                existing_field.ai_extracted_value = field_data.get("ai_extracted_value")
                existing_field.ai_confidence = field_data.get("ai_confidence")
                existing_field.final_value = field_data.get("final_value", field_data.get("ai_extracted_value", ""))
            else:
                new_field = ExtractedData(
                    document_id=document.id,
                    field_name=field_data.get("field_name", ""),
                    field_label=field_data.get("field_label"),
                    ai_extracted_value=field_data.get("ai_extracted_value"),
                    ai_confidence=field_data.get("ai_confidence"),
                    final_value=field_data.get("final_value", field_data.get("ai_extracted_value", "")),
                    is_corrected=False
                )
                db.add(new_field)
        
        executive_summary = ai_service.summarize_document(text_content)
        document.executive_summary = executive_summary
        
        try:
            confidence_value = float(classification_confidence)
            if confidence_value < 0.7:
                document.status = "REVIEW_NEEDED"
            else:
                document.status = "PROCESSED"
        except (ValueError, TypeError):
            document.status = "REVIEW_NEEDED"
        
        document.processing_completed_at = datetime.utcnow()
        db.commit()

        user = db.query(User).filter(User.id == document.upload_user_id).first()
        if user and user.email:
            notification_service.notify_document_processed(
                to_email=user.email,
                document_name=document.original_filename,
                document_id=str(document.id),
                status=document.status,
            )

        logger.info(f"Document processed successfully: {document_id}")

        return {
            "status": "success",
            "document_id": document_id,
            "document_type": doc_type,
            "confidence": classification_confidence
        }
        
    except Exception as exc:
        logger.error(f"Error processing document {document_id}: {exc}")
        
        document = db.query(Document).filter(Document.id == UUID(document_id)).first()
        if document:
            document.status = "ERROR"
            document.processing_error = str(exc)
            document.processing_completed_at = datetime.utcnow()
            db.commit()
        
        raise self.retry(exc=exc)
    
    finally:
        db.close()
