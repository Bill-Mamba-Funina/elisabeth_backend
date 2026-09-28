import logging
from threading import Thread
from django.conf import settings
from django.core.mail import send_mail
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)


def _send_email_task(subject: str, message: str, recipient_list: list = None):
    """Tâche d'envoi d'email via Django (Gmail)."""
    try:
        recipients = recipient_list or getattr(
            settings, "ADMIN_NOTIFICATION_EMAILS", [settings.DEFAULT_FROM_EMAIL]
        )
        send_mail(
            subject=f"[{getattr(settings, 'APP_NAME', 'SODAP')}] {subject}",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi de l'email : {e}")


def _send_whatsapp_task(message: str, recipient_numbers: list = None):
    """Tâche d'envoi de message WhatsApp via Twilio."""
    account_sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    auth_token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_whatsapp_number = getattr(settings, "TWILIO_WHATSAPP_NUMBER", None)

    if not all([account_sid, auth_token, from_whatsapp_number]):
        logger.warning(
            "Configuration Twilio WhatsApp manquante. Notification ignorée."
        )
        return

    numbers = recipient_numbers or getattr(
        settings, "ADMIN_NOTIFICATION_WHATSAPP", []
    )

    try:
        client = TwilioClient(account_sid, auth_token)
        for number in numbers:
            # S'assurer du format 'whatsapp:+243...'
            to_number = number if number.startswith("whatsapp:") else f"whatsapp:{number}"
            client.messages.create(
                body=message,
                from_=from_whatsapp_number,
                to=to_number
            )
    except Exception as e:
        logger.error(f"Erreur lors de l'envoi du message WhatsApp : {e}")


def send_notification(
    subject: str,
    message: str,
    recipient_emails: list = None,
    recipient_whatsapp: list = None,
    send_email: bool = True,
    send_whatsapp: bool = True,
):
    """
    Fonction globale de notification (non bloquante via des Threads).
    Pousse vers Gmail et WhatsApp.
    """
    # 1. Envoi Email (Gmail)
    if send_email:
        Thread(
            target=_send_email_task,
            args=(subject, message, recipient_emails),
            daemon=True,
        ).start()

    # 2. Envoi WhatsApp
    if send_whatsapp:
        full_whatsapp_message = f"*{subject}*\n\n{message}"
        Thread(
            target=_send_whatsapp_task,
            args=(full_whatsapp_message, recipient_whatsapp),
            daemon=True,
        ).start()