import logging
import smtplib
from email.message import EmailMessage
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self):
        self.provider = settings.EMAIL_PROVIDER
        self.sender_email = settings.SENDER_EMAIL

        if self.provider == "SMTP":
            self.smtp_server = settings.SMTP_SERVER
            self.smtp_port = settings.SMTP_PORT
            self.smtp_username = settings.SMTP_USERNAME
            self.smtp_password = settings.SMTP_PASSWORD

    def send_email(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        if self.provider == "CONSOLE":
            logger.info("[EMAIL CONSOLE] To: %s | Subject: %s", to_email, subject)
            logger.info("[EMAIL CONSOLE] Body:\n%s", body)
            return True

        if self.provider == "SMTP":
            try:
                msg = EmailMessage()
                msg.set_content(body)
                if html_body:
                    msg.add_alternative(html_body, subtype="html")
                msg["Subject"] = subject
                msg["From"] = self.sender_email
                msg["To"] = to_email

                try:
                    server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                    server.quit()
                except Exception:
                    server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                    server.quit()

                logger.info("Email sent to %s", to_email)
                return True
            except Exception as e:
                logger.error("Failed to send email to %s: %s", to_email, e)
                return False

        logger.warning("Email provider '%s' not supported", self.provider)
        return False

    def notify_document_uploaded(self, to_email: str, document_name: str, document_id: str) -> bool:
        subject = "SAPI - Documento recibido"
        body = (
            f"Hola,\n\n"
            f'Su documento "{document_name}" ha sido recibido y está en cola para procesamiento.\n\n'
            f"Puede seguir el progreso en:\n{settings.FRONTEND_URL}/documents/{document_id}\n\n"
            f"Gracias por usar SAPI."
        )
        return self.send_email(to_email, subject, body)

    def notify_document_processed(self, to_email: str, document_name: str, document_id: str, status: str) -> bool:
        subject = f"SAPI - Procesamiento de documento: {status}"
        status_msg = (
            "ha sido procesado exitosamente"
            if status == "PROCESSED"
            else f"requiere revisión (estado: {status})"
        )
        body = (
            f"Hola,\n\n"
            f'Su documento "{document_name}" {status_msg}.\n\n'
            f"Ver detalles en:\n{settings.FRONTEND_URL}/documents/{document_id}\n\n"
            f"Gracias por usar SAPI."
        )
        return self.send_email(to_email, subject, body)


notification_service = NotificationService()
