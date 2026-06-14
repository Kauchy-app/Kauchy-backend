import logging
import os

import requests
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_waitlist_welcome_email(recipient_email: str) -> bool:
    """Send waitlist confirmation email through Brevo.

    Returns True when Brevo accepts the request, otherwise False.
    """
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")
    sender_name = os.getenv("BREVO_SENDER_NAME", "Upstart")
    subject = os.getenv("BREVO_WAITLIST_SUBJECT", "You are on the Upstart waitlist")

    if not api_key or not sender_email:
        logger.warning("Brevo waitlist email not sent: missing BREVO_API_KEY or BREVO_SENDER_EMAIL")
        return False

    html_content = render_to_string(
        "waitlist/waitlist_email.html",
        {
            "recipient_email": recipient_email,
        },
    )

    payload = {
        "sender": {
            "email": sender_email,
            "name": sender_name,
        },
        "subject": subject,
        "to": [
            {
                "email": recipient_email,
            }
        ],
        "htmlContent": html_content,
    }

    headers = {
        "accept": "application/json",
        "api-key": api_key,
        "content-type": "application/json",
    }

    try:
        response = requests.post(BREVO_API_URL, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.exception("Brevo waitlist email request failed: %s", exc)
        return False

    return True
