import logging
from typing import Optional

from celery import Celery

from app.core.config import settings


logger = logging.getLogger(__name__)


class MessageBrokerService:
    def __init__(self):
        self.broker_url = settings.CELERY_BROKER_URL
        self.result_backend = settings.CELERY_RESULT_BACKEND
        
        try:
            self.celery_app = Celery(
                'sapi',
                broker=self.broker_url,
                backend=self.result_backend
            )
            self.celery_app.conf.update(
                task_serializer='json',
                accept_content=['json'],
                result_serializer='json',
                timezone='UTC',
                enable_utc=True,
                task_track_started=True,
                task_acks_late=True,
                worker_prefetch_multiplier=1,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Celery: {e}")
            self.celery_app = None
    
    def publish_document_processing(self, document_id: str) -> bool:
        if not self.celery_app:
            logger.error("Celery not initialized")
            return False
        
        try:
            self.celery_app.send_task(
                'app.tasks.document_processing_tasks.process_document_task',
                args=[document_id],
                queue='ai_processing'
            )
            logger.info(f"Document processing task published: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish document processing task: {e}")
            return False
    
    def publish_notification(self, document_id: str, user_id: str, status: str) -> bool:
        if not self.celery_app:
            logger.error("Celery not initialized")
            return False
        
        try:
            self.celery_app.send_task(
                'app.tasks.notification_tasks.send_notification_task',
                args=[document_id, user_id, status],
                queue='notifications'
            )
            logger.info(f"Notification task published for document: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish notification task: {e}")
            return False


message_broker_service = MessageBrokerService()
