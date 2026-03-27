import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.user import User
from app.core.security import get_password_hash, create_refresh_token
from app.core.config import settings


def make_user(db_session: Session, username="testuser", email="test@example.com", is_active=True) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash("password123"),
        role="user",
        is_active=is_active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Login (form)
# ---------------------------------------------------------------------------

def test_login_success(client: TestClient, db_session: Session):
    make_user(db_session)
    response = client.post("/api/v1/auth/login", data={"username": "testuser", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_password(client: TestClient, db_session: Session):
    make_user(db_session)
    response = client.post("/api/v1/auth/login", data={"username": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401


def test_login_unknown_user(client: TestClient, db_session: Session):
    response = client.post("/api/v1/auth/login", data={"username": "ghost", "password": "password123"})
    assert response.status_code == 401


def test_login_inactive_user(client: TestClient, db_session: Session):
    make_user(db_session, is_active=False)
    response = client.post("/api/v1/auth/login", data={"username": "testuser", "password": "password123"})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Login JSON
# ---------------------------------------------------------------------------

def test_login_json_success(client: TestClient, db_session: Session):
    make_user(db_session)
    response = client.post("/api/v1/auth/login/json", json={"username": "testuser", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_json_invalid(client: TestClient, db_session: Session):
    make_user(db_session)
    response = client.post("/api/v1/auth/login/json", json={"username": "testuser", "password": "wrong"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

def test_register_user(client: TestClient, db_session: Session):
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "password123", "full_name": "New User"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"


def test_register_duplicate_email(client: TestClient, db_session: Session):
    make_user(db_session)
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "other", "email": "test@example.com", "password": "password123"},
    )
    assert response.status_code == 400
    assert "Email" in response.json()["detail"]


def test_register_duplicate_username(client: TestClient, db_session: Session):
    make_user(db_session)
    response = client.post(
        "/api/v1/auth/register",
        json={"username": "testuser", "email": "other@example.com", "password": "password123"},
    )
    assert response.status_code == 400
    assert "Username" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Refresh token
# ---------------------------------------------------------------------------

def test_refresh_token_missing(client: TestClient):
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert "missing" in response.json()["detail"].lower()


def test_refresh_token_invalid(client: TestClient):
    client.cookies.set("refresh_token", "invalid.token.here", path="/api/v1/auth/refresh")
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_token_success(client: TestClient, db_session: Session):
    user = make_user(db_session)
    refresh_tok = create_refresh_token(subject=str(user.id))
    client.cookies.set("refresh_token", refresh_tok, path="/api/v1/auth/refresh")
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_refresh_token_inactive_user(client: TestClient, db_session: Session):
    user = make_user(db_session, is_active=False)
    refresh_tok = create_refresh_token(subject=str(user.id))
    client.cookies.set("refresh_token", refresh_tok, path="/api/v1/auth/refresh")
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout(client: TestClient):
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert "Logged out" in response.json()["message"]
