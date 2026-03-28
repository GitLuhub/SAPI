from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.v1.deps import get_db, get_current_user, get_current_superuser
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.db.models.user import User
from app.core.security import get_password_hash
from app.core.audit import log_action


router = APIRouter()


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: User = Depends(get_current_user)
) -> User:
    return current_user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
) -> User:
    user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    
    if user:
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
    
    db.add(user)
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


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
) -> List[User]:
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
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
    user = db.query(User).filter(User.id == user_id).first()
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
    
    for field, value in update_data.items():
        setattr(user, field, value)
    
    db.add(user)
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
    user = db.query(User).filter(User.id == user_id).first()
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
    db.delete(user)
    db.commit()
