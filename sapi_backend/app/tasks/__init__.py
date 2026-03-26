from app.tasks.celery_app import celery_app
from app.tasks.document_processing_tasks import process_document_task
from app.tasks.notification_tasks import send_notification_task

__all__ = [
    "celery_app",
    "process_document_task",
    "send_notification_task",
]
