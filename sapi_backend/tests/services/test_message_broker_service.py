from unittest.mock import MagicMock, patch
from app.services.message_broker_service import MessageBrokerService


def make_broker(celery_ok: bool = True) -> MessageBrokerService:
    with patch("app.services.message_broker_service.Celery") as MockCelery:
        if not celery_ok:
            MockCelery.side_effect = Exception("Redis unavailable")
        broker = MessageBrokerService()
    if celery_ok and broker.celery_app is None:
        # Force a mock celery app in case init path didn't store it
        broker.celery_app = MagicMock()
    return broker


# ---------------------------------------------------------------------------
# publish_document_processing
# ---------------------------------------------------------------------------

def test_publish_document_processing_success():
    broker = MessageBrokerService.__new__(MessageBrokerService)
    broker.celery_app = MagicMock()
    result = broker.publish_document_processing("doc-id-123")
    assert result is True
    broker.celery_app.send_task.assert_called_once()
    call_kwargs = broker.celery_app.send_task.call_args
    assert call_kwargs[1]["queue"] == "ai_processing"


def test_publish_document_processing_no_celery():
    broker = MessageBrokerService.__new__(MessageBrokerService)
    broker.celery_app = None
    result = broker.publish_document_processing("doc-id-123")
    assert result is False


def test_publish_document_processing_send_task_raises():
    broker = MessageBrokerService.__new__(MessageBrokerService)
    broker.celery_app = MagicMock()
    broker.celery_app.send_task.side_effect = Exception("connection error")
    result = broker.publish_document_processing("doc-id-123")
    assert result is False


# ---------------------------------------------------------------------------
# publish_notification
# ---------------------------------------------------------------------------

def test_publish_notification_success():
    broker = MessageBrokerService.__new__(MessageBrokerService)
    broker.celery_app = MagicMock()
    result = broker.publish_notification("doc-id", "user-id", "PROCESSED")
    assert result is True
    broker.celery_app.send_task.assert_called_once()
    call_kwargs = broker.celery_app.send_task.call_args
    assert call_kwargs[1]["queue"] == "notifications"


def test_publish_notification_no_celery():
    broker = MessageBrokerService.__new__(MessageBrokerService)
    broker.celery_app = None
    result = broker.publish_notification("doc-id", "user-id", "PROCESSED")
    assert result is False


def test_publish_notification_send_task_raises():
    broker = MessageBrokerService.__new__(MessageBrokerService)
    broker.celery_app = MagicMock()
    broker.celery_app.send_task.side_effect = Exception("timeout")
    result = broker.publish_notification("doc-id", "user-id", "PROCESSED")
    assert result is False
