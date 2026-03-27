import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.core.security import get_password_hash, create_access_token
from datetime import timedelta
import uuid

def create_test_token(user: User):
    return create_access_token(subject=str(user.id), expires_delta=timedelta(minutes=30))

def test_get_users_superuser(client: TestClient, db_session: Session):
    user = User(username="admin", email="admin@test.com", hashed_password="pw", role="admin", is_active=True, is_superuser=True)
    db_session.add(user)
    db_session.commit()
    token = create_test_token(user)
    
    response = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

def test_update_user_me(client: TestClient, db_session: Session):
    user = User(username="update_me", email="updateme@test.com", hashed_password="pw", role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    token = create_test_token(user)
    
    response = client.put("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"}, json={"full_name": "New Name"})
    assert response.status_code == 200
    assert response.json()["full_name"] == "New Name"

def test_get_user_by_id(client: TestClient, db_session: Session):
    user = User(username="admin", email="admin@test.com", hashed_password="pw", role="admin", is_active=True, is_superuser=True)
    other = User(username="other", email="other@test.com", hashed_password="pw", role="user", is_active=True)
    db_session.add(user)
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    token = create_test_token(user)
    
    response = client.get(f"/api/v1/users/{other.id}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["username"] == "other"

def test_create_user_by_admin(client: TestClient, db_session: Session):
    user = User(username="admin", email="admin@test.com", hashed_password="pw", role="admin", is_active=True, is_superuser=True)
    db_session.add(user)
    db_session.commit()
    token = create_test_token(user)
    
    response = client.post("/api/v1/users", headers={"Authorization": f"Bearer {token}"}, json={"username": "newu", "email": "newu@test.com", "password": "pw"})
    assert response.status_code == 200
