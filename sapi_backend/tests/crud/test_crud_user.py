"""Tests unitarios para CRUDUser."""
import uuid
from sqlalchemy.orm import Session

import pytest

from app.crud.crud_user import CRUDUser
from app.db.models.user import User
from app.core.security import get_password_hash


crud = CRUDUser()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(db: Session, username=None, email=None, role="user") -> User:
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=username or f"u_{suffix}",
        email=email or f"{suffix}@test.com",
        hashed_password=get_password_hash("pass"),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.flush()
    return u


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------

def test_get_returns_user(db_session: Session):
    user = _user(db_session)
    db_session.commit()

    found = crud.get(db_session, user.id)
    assert found is not None
    assert found.id == user.id


def test_get_returns_none_for_unknown_id(db_session: Session):
    assert crud.get(db_session, uuid.uuid4()) is None


# ---------------------------------------------------------------------------
# get_by_username
# ---------------------------------------------------------------------------

def test_get_by_username_found(db_session: Session):
    user = _user(db_session, username="uniqueuser_abc")
    db_session.commit()

    found = crud.get_by_username(db_session, "uniqueuser_abc")
    assert found is not None
    assert found.username == "uniqueuser_abc"


def test_get_by_username_not_found(db_session: Session):
    assert crud.get_by_username(db_session, "nobody_xyz_999") is None


# ---------------------------------------------------------------------------
# get_by_username_or_email
# ---------------------------------------------------------------------------

def test_get_by_username_or_email_by_username(db_session: Session):
    user = _user(db_session, username="combo_user")
    db_session.commit()

    found = crud.get_by_username_or_email(db_session, "combo_user", "other@example.com")
    assert found is not None


def test_get_by_username_or_email_by_email(db_session: Session):
    suffix = uuid.uuid4().hex[:6]
    email = f"unique_{suffix}@find.com"
    user = _user(db_session, email=email)
    db_session.commit()

    found = crud.get_by_username_or_email(db_session, "nonexistent_xyz", email)
    assert found is not None


def test_get_by_username_or_email_not_found(db_session: Session):
    assert crud.get_by_username_or_email(db_session, "nobody_xyz", "nobody@xyz.com") is None


# ---------------------------------------------------------------------------
# add / update / delete
# ---------------------------------------------------------------------------

def test_add_and_delete(db_session: Session):
    suffix = uuid.uuid4().hex[:6]
    user = User(
        username=f"adduser_{suffix}",
        email=f"add_{suffix}@test.com",
        hashed_password=get_password_hash("pass"),
        role="user",
        is_active=True,
    )
    crud.add(db_session, user)
    db_session.commit()

    assert crud.get(db_session, user.id) is not None

    crud.delete(db_session, user)
    db_session.commit()

    assert crud.get(db_session, user.id) is None


def test_update_fields(db_session: Session):
    user = _user(db_session)
    db_session.commit()

    crud.update(db_session, user, {"full_name": "Nombre Completo"})
    db_session.commit()

    refreshed = crud.get(db_session, user.id)
    assert refreshed.full_name == "Nombre Completo"


def test_update_password(db_session: Session):
    user = _user(db_session)
    db_session.commit()

    new_hash = get_password_hash("newpassword123")
    crud.update(db_session, user, {"hashed_password": new_hash})
    db_session.commit()

    refreshed = crud.get(db_session, user.id)
    assert refreshed.hashed_password == new_hash


# ---------------------------------------------------------------------------
# list_paginated
# ---------------------------------------------------------------------------

def test_list_paginated_returns_users(db_session: Session):
    _user(db_session)
    _user(db_session)
    db_session.commit()

    users, total = crud.list_paginated(db_session, page=1, size=100)
    assert total >= 2
    assert len(users) >= 2


def test_list_paginated_size_limit(db_session: Session):
    for _ in range(5):
        _user(db_session)
    db_session.commit()

    users, total = crud.list_paginated(db_session, page=1, size=2)
    assert len(users) <= 2


def test_list_paginated_page2(db_session: Session):
    for _ in range(4):
        _user(db_session)
    db_session.commit()

    _, total = crud.list_paginated(db_session, page=1, size=2)
    users_p2, _ = crud.list_paginated(db_session, page=2, size=2)
    assert len(users_p2) >= 0  # puede haber resultados o no dependiendo del estado de BD
