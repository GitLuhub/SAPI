from celery import Celery

from app.core.config import settings


celery_app = Celery(
    'sapi',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.tasks.document_processing_tasks',
        'app.tasks.notification_tasks',
    ]
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        'app.tasks.document_processing_tasks.*': {'queue': 'ai_processing'},
        'app.tasks.notification_tasks.*': {'queue': 'notifications'},
    },
    task_default_queue='default',
)
