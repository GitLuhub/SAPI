from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models.user import User


class CRUDUser:
    """Operaciones de base de datos para User."""

    def get(self, db: Session, id: UUID) -> Optional[User]:
        return db.query(User).filter(User.id == id).first()

    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    def get_by_username_or_email(
        self, db: Session, username: str, email: str
    ) -> Optional[User]:
        return (
            db.query(User)
            .filter((User.username == username) | (User.email == email))
            .first()
        )

    def list_paginated(
        self, db: Session, page: int, size: int
    ) -> Tuple[List[User], int]:
        total = db.query(User).count()
        offset = (page - 1) * size
        users = db.query(User).offset(offset).limit(size).all()
        return users, total

    def add(self, db: Session, user: User) -> None:
        """Agrega el usuario a la sesión (sin commit)."""
        db.add(user)

    def update(self, db: Session, user: User, update_data: dict) -> None:
        """Aplica update_data al usuario y lo agrega a la sesión (sin commit)."""
        for field, value in update_data.items():
            setattr(user, field, value)
        db.add(user)

    def delete(self, db: Session, user: User) -> None:
        """Elimina el usuario de la sesión (sin commit)."""
        db.delete(user)


crud_user = CRUDUser()
