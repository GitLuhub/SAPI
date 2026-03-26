import logging
from typing import Optional
import smtplib
from email.message import EmailMessage
import json

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

    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        if self.provider == "LOCAL_DUMMY":
            logger.info(f"[DUMMY EMAIL] To: {to_email} | Subject: {subject} | Body: {body}")
            return True
            
        if self.provider == "SMTP":
            try:
                msg = EmailMessage()
                msg.set_content(body)
                msg["Subject"] = subject
                msg["From"] = self.sender_email
                msg["To"] = to_email

                # Try TLS connection
                try:
                    server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                    server.quit()
                    logger.info(f"Email sent successfully to {to_email}")
                    return True
                except Exception as e:
                    # Fallback to SSL if TLS fails (some providers use port 465 for SSL)
                    server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
                    server.quit()
                    logger.info(f"Email sent successfully to {to_email} via SSL")
                    return True
            except Exception as e:
                logger.error(f"Failed to send email: {e}")
                return False
                
        logger.warning(f"Email provider {self.provider} not supported or implemented")
        return False

    def notify_document_processed(self, to_email: str, document_name: str, document_id: str, status: str) -> bool:
        subject = f"SAPI - Document Processing {status}"
        
        status_msg = "has been processed successfully" if status == "PROCESSED" else f"processing resulted in status: {status}"
        
        body = f"""
Hello,

Your document "{document_name}" {status_msg}.

You can view the details by logging into the SAPI platform or visiting this link:
{settings.FRONTEND_URL}/documents/{document_id}

Thank you for using SAPI.
"""
        return self.send_email(to_email, subject, body)


notification_service = NotificationService()
