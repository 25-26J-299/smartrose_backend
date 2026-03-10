"""Email notification delivery via SMTP (Gmail)."""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _send_email_sync(to_email: str, subject: str, message: str) -> None:
    """Blocking SMTP send. Run in thread to avoid blocking event loop."""
    smtp_email = (getattr(settings, "SMTP_EMAIL", None) or "").strip()
    smtp_password = getattr(settings, "SMTP_PASSWORD", None) or ""
    if not smtp_email or not smtp_password:
        logger.warning("Email skipped: SMTP_EMAIL or SMTP_PASSWORD not configured")
        return

    to_email = (to_email or "").strip()
    if not to_email:
        logger.debug("Email skipped: no recipient")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_email
    msg["To"] = to_email
    msg.attach(MIMEText(message, "plain"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())
        logger.info("Email sent", extra={"to": to_email, "subject": subject[:50]})
    except Exception as e:
        logger.exception("Email send failed: %s", e)
        raise


async def send_email_notification(
    to_email: str,
    subject: str,
    message: str,
) -> bool:
    """
    Send an email notification via SMTP (Gmail, port 587, TLS).

    Args:
        to_email: Recipient email address
        subject: Email subject
        message: Plain-text body

    Returns:
        True if sent successfully, False if skipped or failed
    """
    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, message)
        return True
    except Exception as e:
        logger.exception("Email notification failed: %s", e)
        return False
