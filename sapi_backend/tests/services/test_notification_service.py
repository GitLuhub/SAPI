import pytest
from unittest.mock import patch, MagicMock

from app.services.notification_service import NotificationService


def make_service(provider="CONSOLE") -> NotificationService:
    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.EMAIL_PROVIDER = provider
        mock_settings.SENDER_EMAIL = "noreply@sapi.local"
        mock_settings.SMTP_SERVER = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USERNAME = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_settings.FRONTEND_URL = "http://localhost:3000"
        svc = NotificationService()
    svc.provider = provider
    svc.sender_email = "noreply@sapi.local"
    if provider == "SMTP":
        svc.smtp_server = "smtp.example.com"
        svc.smtp_port = 587
        svc.smtp_username = "user"
        svc.smtp_password = "pass"
    return svc


# ---------------------------------------------------------------------------
# CONSOLE provider
# ---------------------------------------------------------------------------

def test_console_provider_returns_true():
    svc = make_service("CONSOLE")
    result = svc.send_email("user@example.com", "Subject", "Body")
    assert result is True


def test_console_provider_logs(caplog):
    import logging
    svc = make_service("CONSOLE")
    with caplog.at_level(logging.INFO, logger="app.services.notification_service"):
        svc.send_email("user@example.com", "Test Subject", "Test Body")
    assert "user@example.com" in caplog.text
    assert "Test Subject" in caplog.text


# ---------------------------------------------------------------------------
# Unsupported provider
# ---------------------------------------------------------------------------

def test_unsupported_provider_returns_false():
    svc = make_service("SENDGRID")
    result = svc.send_email("user@example.com", "Subject", "Body")
    assert result is False


# ---------------------------------------------------------------------------
# SMTP provider
# ---------------------------------------------------------------------------

def test_smtp_provider_sends_via_tls():
    svc = make_service("SMTP")
    mock_server = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_server):
        result = svc.send_email("user@example.com", "Subject", "Body")
    assert result is True
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once()
    mock_server.send_message.assert_called_once()


def test_smtp_send_with_html_body():
    """html_body triggers msg.add_alternative (line 33)."""
    svc = make_service("SMTP")
    mock_server = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_server):
        result = svc.send_email(
            "user@example.com", "Subject", "Plain body", html_body="<b>HTML body</b>"
        )
    assert result is True
    mock_server.send_message.assert_called_once()


def test_smtp_provider_fallback_ssl():
    svc = make_service("SMTP")
    mock_ssl_server = MagicMock()
    with patch("smtplib.SMTP", side_effect=Exception("TLS failed")):
        with patch("smtplib.SMTP_SSL", return_value=mock_ssl_server):
            result = svc.send_email("user@example.com", "Subject", "Body")
    assert result is True
    mock_ssl_server.send_message.assert_called_once()


def test_smtp_provider_failure_returns_false():
    svc = make_service("SMTP")
    with patch("smtplib.SMTP", side_effect=Exception("Connection refused")):
        with patch("smtplib.SMTP_SSL", side_effect=Exception("SSL failed")):
            result = svc.send_email("user@example.com", "Subject", "Body")
    assert result is False


# ---------------------------------------------------------------------------
# Notification helpers
# ---------------------------------------------------------------------------

def test_notify_document_uploaded():
    svc = make_service("CONSOLE")
    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.FRONTEND_URL = "http://localhost:3000"
        result = svc.notify_document_uploaded("user@example.com", "factura.pdf", "abc-123")
    assert result is True


def test_notify_document_processed_success():
    svc = make_service("CONSOLE")
    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.FRONTEND_URL = "http://localhost:3000"
        result = svc.notify_document_processed("user@example.com", "contrato.pdf", "abc-456", "PROCESSED")
    assert result is True


def test_notify_document_processed_review():
    svc = make_service("CONSOLE")
    with patch("app.services.notification_service.settings") as mock_settings:
        mock_settings.FRONTEND_URL = "http://localhost:3000"
        result = svc.notify_document_processed("user@example.com", "contrato.pdf", "abc-789", "REVIEW_NEEDED")
    assert result is True
