import os
import uuid as uuid_lib
from datetime import datetime, date
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status, UploadFile, File, Query
from sqlalchemy.orm import Session, joinedload

from app.core.limiter import limiter

from app.api.v1.deps import get_db, get_current_user, check_document_access, check_document_write_access
from app.core.audit import log_action
from app.schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentStatusResponse,
    DocumentDetailResponse, DocumentTypeResponse, ExtractedFieldResponse,
    ExtractedDataUpdateList, DocumentStatus
)
from app.schemas.common import MessageResponse, PaginatedResponse
from app.db.models.user import User
from app.db.models.document import Document, DocumentType
from app.db.models.extracted_data import ExtractedData
from app.services.storage_service import StorageService
from app.services.message_broker_service import MessageBrokerService
from app.services.notification_service import notification_service


router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024


def validate_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )


@router.get("/", response_model=PaginatedResponse[DocumentListResponse])
async def list_documents(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    status_filter: Optional[DocumentStatus] = Query(None, alias="status"),
    document_type_id: Optional[UUID] = None,
    search_query: Optional[str] = None,
    date_from: Optional[date] = Query(None, description="Filter documents uploaded from this date (inclusive)"),
    date_to: Optional[date] = Query(None, description="Filter documents uploaded up to this date (inclusive)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaginatedResponse:
    query = db.query(Document).options(joinedload(Document.document_type))

    if status_filter:
        query = query.filter(Document.status == status_filter.value)

    if document_type_id:
        query = query.filter(Document.document_type_id == document_type_id)

    if search_query:
        query = query.filter(Document.original_filename.ilike(f"%{search_query}%"))

    if date_from:
        query = query.filter(Document.created_at >= datetime.combine(date_from, datetime.min.time()))

    if date_to:
        query = query.filter(Document.created_at <= datetime.combine(date_to, datetime.max.time()))

    total = query.count()

    offset = (page - 1) * size
    documents = query.order_by(Document.created_at.desc()).offset(offset).limit(size).all()

    items = [
        DocumentListResponse(
            id=doc.id,
            original_filename=doc.original_filename,
            status=DocumentStatus(doc.status),
            document_type_name=doc.document_type.name if doc.document_type else None,
            classification_confidence=doc.classification_confidence,
            created_at=doc.created_at,
        )
        for doc in documents
    ]

    pages = (total + size - 1) // size if size > 0 else 0

    return PaginatedResponse(items=items, total=total, page=page, size=size, pages=pages)


@router.post("/", response_model=DocumentStatusResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_type_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DocumentStatusResponse:
    validate_file(file)

    if document_type_id is not None:
        if not db.query(DocumentType).filter(DocumentType.id == document_type_id, DocumentType.is_active == True).first():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Document type '{document_type_id}' not found or inactive",
            )

    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE} bytes"
        )
    
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )
    
    doc_uuid = uuid_lib.uuid4()
    ext = os.path.splitext(file.filename)[1].lower()
    storage_path = f"documents/{current_user.id}/{doc_uuid}{ext}"
    
    storage_service = StorageService()
    await storage_service.upload_file(storage_path, content, file.content_type)
    
    document = Document(
        id=doc_uuid,
        original_filename=file.filename,
        storage_path=storage_path,
        file_size=str(file_size),
        mime_type=file.content_type,
        status=DocumentStatus.UPLOADED.value,
        upload_user_id=current_user.id,
        document_type_id=document_type_id
    )
    
    db.add(document)
    log_action(
        db,
        action="document.upload",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(doc_uuid),
        details=f"filename={file.filename} size={file_size}",
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(document)

    message_broker = MessageBrokerService()
    message_broker.publish_document_processing(str(document.id))

    if current_user.email:
        notification_service.notify_document_uploaded(
            to_email=current_user.email,
            document_name=file.filename,
            document_id=str(document.id),
        )

    return DocumentStatusResponse(
        id=document.id,
        status=DocumentStatus.UPLOADED,
        message="Document uploaded successfully and queued for processing."
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    check_document_access(document, current_user)
    return document


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DocumentStatusResponse:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    check_document_access(document, current_user)

    status_messages = {
        "UPLOADED": "Document uploaded and waiting for processing.",
        "PROCESSING": "Document is being processed by the AI.",
        "PROCESSED": "Document processed successfully.",
        "REVIEW_NEEDED": "Document processed but needs review.",
        "ERROR": f"Processing error: {document.processing_error or 'Unknown error'}"
    }
    
    return DocumentStatusResponse(
        id=document.id,
        status=DocumentStatus(document.status),
        message=status_messages.get(document.status, "Unknown status")
    )


@router.get("/{document_id}/data", response_model=DocumentDetailResponse)
async def get_document_data(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> DocumentDetailResponse:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    check_document_access(document, current_user)

    doc_type = None
    if document.document_type_id:
        doc_type = db.query(DocumentType).filter(DocumentType.id == document.document_type_id).first()
    
    extracted_fields = db.query(ExtractedData).filter(
        ExtractedData.document_id == document_id
    ).all()
    
    from app.schemas.document import ExtractedFieldResponse
    fields = [
        ExtractedFieldResponse(
            field_name=ef.field_name,
            field_label=ef.field_label,
            ai_extracted_value=ef.ai_extracted_value,
            ai_confidence=ef.ai_confidence,
            final_value=ef.final_value,
            is_corrected=ef.is_corrected,
            corrected_at=ef.corrected_at
        )
        for ef in extracted_fields
    ]
    
    doc_type_response = None
    if doc_type:
        doc_type_response = DocumentTypeResponse(
            id=doc_type.id,
            name=doc_type.name,
            description=doc_type.description,
            is_active=doc_type.is_active,
            created_at=doc_type.created_at,
            updated_at=doc_type.updated_at
        )
    
    return DocumentDetailResponse(
        id=document.id,
        original_filename=document.original_filename,
        file_size=document.file_size,
        mime_type=document.mime_type,
        status=DocumentStatus(document.status),
        document_type=doc_type_response,
        classification_confidence=document.classification_confidence,
        executive_summary=document.executive_summary,
        extracted_fields=fields,
        processing_started_at=document.processing_started_at,
        processing_completed_at=document.processing_completed_at,
        processing_error=document.processing_error,
        created_at=document.created_at,
        updated_at=document.updated_at
    )


@router.put("/{document_id}/data", response_model=MessageResponse)
async def update_document_data(
    document_id: UUID,
    updates: ExtractedDataUpdateList,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> MessageResponse:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    check_document_write_access(current_user)

    for update in updates.updates:
        extracted_field = db.query(ExtractedData).filter(
            ExtractedData.document_id == document_id,
            ExtractedData.field_name == update.field_name
        ).first()
        
        if extracted_field:
            extracted_field.final_value = update.new_value
            extracted_field.is_corrected = True
            extracted_field.corrected_by_user_id = current_user.id
            extracted_field.corrected_at = datetime.utcnow()
        else:
            new_field = ExtractedData(
                document_id=document_id,
                field_name=update.field_name,
                final_value=update.new_value,
                is_corrected=True,
                corrected_by_user_id=current_user.id,
                corrected_at=datetime.utcnow()
            )
            db.add(new_field)
    
    if document.status == DocumentStatus.REVIEW_NEEDED.value:
        review_needed_count = db.query(ExtractedData).filter(
            ExtractedData.document_id == document_id,
            ExtractedData.is_corrected == False
        ).count()
        
        if review_needed_count == 0:
            document.status = DocumentStatus.PROCESSED.value
    
    log_action(
        db,
        action="document.correct_fields",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(document_id),
        details=f"fields={[u.field_name for u in updates.updates]}",
    )
    db.commit()

    return MessageResponse(message="Document data updated successfully.")


@router.get("/{document_id}/download")
async def download_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> dict:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    check_document_access(document, current_user)

    storage_service = StorageService()
    file_content = await storage_service.download_file(document.storage_path)

    from fastapi.responses import Response
    return Response(
        content=file_content,
        media_type=document.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{document.original_filename}"'
        }
    )


@router.get("/{document_id}/preview")
async def preview_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    check_document_access(document, current_user)

    storage_service = StorageService()
    file_content = await storage_service.download_file(document.storage_path)

    from fastapi.responses import Response
    return Response(
        content=file_content,
        media_type=document.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{document.original_filename}"'},
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    check_document_access(document, current_user)

    storage_service = StorageService()
    try:
        await storage_service.delete_file(document.storage_path)
    except Exception:
        pass  # No bloquear el borrado de BD si el archivo ya no existe en storage

    log_action(
        db,
        action="document.delete",
        user_id=current_user.id,
        entity_type="document",
        entity_id=str(document_id),
        details=f"filename={document.original_filename}",
    )
    db.delete(document)
    db.commit()


@router.get("/types/", response_model=List[DocumentTypeResponse])
async def list_document_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[DocumentType]:
    types = db.query(DocumentType).filter(DocumentType.is_active == True).all()
    return types
