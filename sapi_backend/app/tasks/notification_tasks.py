import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models.user import User
from app.db.models.document import Document
from app.services.notification_service import notification_service


logger = logging.getLogger(__name__)


@celery_app.task(bind=True)
def send_notification_task(self, document_id: str, user_id: str, status: str) -> dict:
    db: Session = SessionLocal()
    
    try:
        user = db.query(User).filter(User.id == UUID(user_id)).first()
        document = db.query(Document).filter(Document.id == UUID(document_id)).first()
        
        if not user:
            logger.warning(f"User not found: {user_id}")
            return {"status": "skipped", "reason": "User not found"}
        
        if not document:
            logger.warning(f"Document not found: {document_id}")
            return {"status": "skipped", "reason": "Document not found"}
        
        subject = f"SAPI: Documento {status.lower().replace('_', ' ')}"
        
        if status == "PROCESSED":
            message = f"""Su documento '{document.original_filename}' ha sido procesado exitosamente.

Puede revisar los datos extraídos accediendo a la plataforma SAPI.

Saludos,
Equipo SAPI
"""
        elif status == "REVIEW_NEEDED":
            message = f"""Su documento '{document.original_filename}' requiere revisión.

Algunos campos no pudieron ser extraídos con suficiente confianza. Por favor, revise y complete la información.

Saludos,
Equipo SAPI
"""
        elif status == "ERROR":
            message = f"""Hubo un error al procesar su documento '{document.original_filename}'.

Por favor, intente subir el documento nuevamente o contacte al soporte técnico.

Saludos,
Equipo SAPI
"""
        else:
            message = f"""El estado de su documento '{document.original_filename}' ha cambiado a: {status}

Saludos,
Equipo SAPI
"""
        
        logger.info(f"Notification would be sent to {user.email}: {subject}")
        logger.debug(f"Notification message:\n{message}")
        
        notification_service.send_email(user.email, subject, message)
        
        logger.info(f"Email notification sent for user {user_id} regarding document {document_id}")
        
        return {
            "status": "success",
            "document_id": document_id,
            "user_id": user_id,
            "email": user.email
        }
        
    except Exception as exc:
        logger.error(f"Error sending notification: {exc}")
        return {"status": "error", "message": str(exc)}
    
    finally:
        db.close()
