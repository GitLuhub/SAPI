import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.core.security import get_password_hash, create_access_token
from datetime import timedelta
import uuid


def create_test_token(user: User):
    return create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=30))


def make_admin(db_session: Session, username="admin2", email="admin2@test.com") -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash("adminpass"),
        role="admin",
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def make_regular_user(db_session: Session, username="regular2", email="regular2@test.com") -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash("userpass"),
        role="user",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# GET /users/ — list users (superuser only)
# ---------------------------------------------------------------------------

def test_get_users_superuser(client: TestClient, db_session: Session):
    admin = make_admin(db_session)
    token = create_test_token(admin)
    response = client.get("/api/v1/users/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_users_forbidden_for_regular_user(client: TestClient, db_session: Session):
    user = make_regular_user(db_session)
    token = create_test_token(user)
    response = client.get("/api/v1/users/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /users/ — create user (superuser only)
# ---------------------------------------------------------------------------

def test_create_user_by_admin(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_create", email="admin_create@test.com")
    token = create_test_token(admin)
    response = client.post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "newuser2", "email": "newuser2@test.com", "password": "pass123"},
    )
    assert response.status_code == 201
    assert response.json()["username"] == "newuser2"


def test_create_user_duplicate_rejected(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_dup", email="admin_dup@test.com")
    existing = make_regular_user(db_session, username="existing_u", email="existing_u@test.com")
    token = create_test_token(admin)
    response = client.post(
        "/api/v1/users/",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "existing_u", "email": "other@test.com", "password": "pass123"},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /users/{user_id} — get user by id (superuser only)
# ---------------------------------------------------------------------------

def test_get_user_by_id(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_getid", email="admin_getid@test.com")
    other = make_regular_user(db_session, username="other_get", email="other_get@test.com")
    token = create_test_token(admin)
    response = client.get(f"/api/v1/users/{other.id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "other_get"


def test_get_user_by_id_not_found(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_nf", email="admin_nf@test.com")
    token = create_test_token(admin)
    response = client.get(f"/api/v1/users/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /users/{user_id} — update user (superuser only)
# ---------------------------------------------------------------------------

def test_update_user_by_admin(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_upd", email="admin_upd@test.com")
    target = make_regular_user(db_session, username="target_upd", email="target_upd@test.com")
    token = create_test_token(admin)
    response = client.put(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Updated Name"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Updated Name"


def test_update_user_not_found(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_upd_nf", email="admin_upd_nf@test.com")
    token = create_test_token(admin)
    response = client.put(
        f"/api/v1/users/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Ghost"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /users/{user_id} — delete user (superuser only)
# ---------------------------------------------------------------------------

def test_delete_user(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_del", email="admin_del@test.com")
    target = make_regular_user(db_session, username="target_del", email="target_del@test.com")
    token = create_test_token(admin)
    response = client.delete(f"/api/v1/users/{target.id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 204


def test_delete_user_not_found(client: TestClient, db_session: Session):
    admin = make_admin(db_session, username="admin_del_nf", email="admin_del_nf@test.com")
    token = create_test_token(admin)
    response = client.delete(f"/api/v1/users/{uuid.uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /users/{user_id} — update with password and role (lines 98, 101)
# ---------------------------------------------------------------------------

def test_update_user_password(client: TestClient, db_session: Session):
    """PUT with password field triggers hashing (line 98)."""
    admin = make_admin(db_session, username="admin_pwd", email="admin_pwd@test.com")
    target = make_regular_user(db_session, username="target_pwd", email="target_pwd@test.com")
    token = create_test_token(admin)
    response = client.put(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "newSecurePass123"},
    )
    assert response.status_code == 200
    # Verify password was actually changed (hashed_password should differ from plaintext)
    db_session.refresh(target)
    assert target.hashed_password != "newSecurePass123"


def test_update_user_role(client: TestClient, db_session: Session):
    """PUT with role field triggers role.value extraction (line 101)."""
    admin = make_admin(db_session, username="admin_role", email="admin_role@test.com")
    target = make_regular_user(db_session, username="target_role", email="target_role@test.com")
    token = create_test_token(admin)
    response = client.put(
        f"/api/v1/users/{target.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "document_reviewer"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "document_reviewer"
