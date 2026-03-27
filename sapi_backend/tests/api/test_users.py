from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.db.models.user import User
from app.core.security import get_password_hash, create_access_token
from datetime import timedelta

def create_test_token(user: User):
    access_token_expires = timedelta(minutes=30)
    return create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )

def test_get_current_user_me(client: TestClient, db_session: Session):
    user = User(
        username="meuser",
        email="me@example.com",
        hashed_password=get_password_hash("password123"),
        role="user",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    token = create_test_token(user)
    
    response = client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meuser"
    assert data["email"] == "me@example.com"
