import uuid
from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy.orm import Session

from app.db.models.document import Document
from app.db.models.user import User
from app.tasks.notification_tasks import send_notification_task


def _setup(db: Session):
    user = User(
        id=uuid.uuid4(),
        username="notif_user",
        email="notif@test.com",
        hashed_password="hash",
        role="user",
    )
    doc = Document(
        id=uuid.uuid4(),
        original_filename="invoice.pdf",
        storage_path="path/invoice.pdf",
        file_size="200",
        mime_type="application/pdf",
        status="PROCESSED",
        upload_user_id=user.id,
    )
    db.add(user)
    db.add(doc)
    db.commit()
    return user, doc


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("status_val", ["PROCESSED", "REVIEW_NEEDED", "ERROR", "UPLOADED"])
def test_send_notification_task_all_statuses(db_session: Session, status_val: str):
    user, doc = _setup(db_session)
    with patch("app.tasks.notification_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        with patch("app.tasks.notification_tasks.notification_service") as mock_notif:
            mock_notif.send_email.return_value = True
            result = send_notification_task(str(doc.id), str(user.id), status_val)

    assert result["status"] == "success"
    assert result["email"] == "notif@test.com"
    mock_notif.send_email.assert_called_once()


# ---------------------------------------------------------------------------
# User not found
# ---------------------------------------------------------------------------

def test_send_notification_task_user_not_found(db_session: Session):
    _, doc = _setup(db_session)
    with patch("app.tasks.notification_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = send_notification_task(str(doc.id), str(uuid.uuid4()), "PROCESSED")

    assert result["status"] == "skipped"
    assert "User" in result["reason"]


# ---------------------------------------------------------------------------
# Document not found
# ---------------------------------------------------------------------------

def test_send_notification_task_document_not_found(db_session: Session):
    user, _ = _setup(db_session)
    with patch("app.tasks.notification_tasks.SessionLocal", return_value=db_session):
        db_session.close = MagicMock()
        result = send_notification_task(str(uuid.uuid4()), str(user.id), "PROCESSED")

    assert result["status"] == "skipped"
    assert "Document" in result["reason"]
