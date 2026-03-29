from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.v1.deps import get_db, get_current_user, get_current_superuser
from app.crud import crud_user, crud_document, crud_extracted_data
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse,
    AccountDeleteRequest, UserDataExport, DocumentExport, ExtractedFieldExport,
)
from app.schemas.common import PaginatedResponse
from app.db.models.user import User
from app.core.security import get_password_hash, verify_password
from app.core.audit import log_action
from app.services.storage_service import StorageService


router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: User = Depends(get_current_user)
) -> User:
    return current_user


@router.get("/me/export", response_model=UserDataExport)
async def export_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserDataExport:
    """J1 GDPR — exporta todos los datos personales del usuario autenticado."""
    documents_db, _ = crud_document.list_filtered(
        db, page=1, size=100_000, upload_user_id=current_user.id
    )

    docs_export: List[DocumentExport] = []
    for doc in documents_db:
        fields_db = crud_extracted_data.get_by_document(db, doc.id)
        fields_export = [
            ExtractedFieldExport(
                field_name=f.field_name,
                field_label=f.field_label,
                ai_extracted_value=f.ai_extracted_value,
                final_value=f.final_value,
                is_corrected=f.is_corrected,
                corrected_at=f.corrected_at,
            )
            for f in fields_db
        ]
        docs_export.append(
            DocumentExport(
                id=doc.id,
                original_filename=doc.original_filename,
                status=doc.status,
                mime_type=doc.mime_type,
                file_size=doc.file_size,
                created_at=doc.created_at,
                extracted_fields=fields_export,
            )
        )

    return UserDataExport(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        created_at=current_user.created_at,
        exported_at=datetime.utcnow(),
        documents=docs_export,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_account(
    body: AccountDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """J2 GDPR — elimina la cuenta, documentos, campos y archivos del usuario (derecho al olvido)."""
    if not verify_password(body.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect password",
        )

    # Eliminar archivos del storage (best-effort)
    documents_db, _ = crud_document.list_filtered(
        db, page=1, size=100_000, upload_user_id=current_user.id
    )
    storage_service = StorageService()
    for doc in documents_db:
        try:
            await storage_service.delete_file(doc.storage_path)
        except Exception:
            pass

    log_action(
        db,
        action="user.self_delete",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(current_user.id),
        details=f"username={current_user.username} (GDPR right to erasure)",
    )

    # Eliminar documentos en BD (ExtractedData en cascade); luego el usuario
    for doc in documents_db:
        crud_document.delete(db, doc)

    crud_user.delete(db, current_user)
    db.commit()


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
) -> User:
    if crud_user.get_by_username_or_email(db, user_in.username, user_in.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username or email already exists"
        )

    user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        role=user_in.role.value,
        hashed_password=get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False
    )

    crud_user.add(db, user)
    log_action(
        db,
        action="user.create",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user.id),
        details=f"username={user_in.username} role={user_in.role.value}",
    )
    db.commit()
    db.refresh(user)

    return user


@router.get("/", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser),
) -> PaginatedResponse:
    users, total = crud_user.list_paginated(db, page=page, size=size)
    pages = (total + size - 1) // size if size > 0 else 0
    return PaginatedResponse(items=users, total=total, page=page, size=size, pages=pages)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
) -> User:
    user = crud_user.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
) -> User:
    user = crud_user.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    update_data = user_in.model_dump(exclude_unset=True)

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    if "role" in update_data and update_data["role"]:
        update_data["role"] = update_data["role"].value

    crud_user.update(db, user, update_data)
    log_action(
        db,
        action="user.update",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user_id),
        details=f"fields={list(update_data.keys())}",
    )
    db.commit()
    db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
) -> None:
    user = crud_user.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    log_action(
        db,
        action="user.delete",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user_id),
        details=f"username={user.username}",
    )
    crud_user.delete(db, user)
    db.commit()
