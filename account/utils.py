from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailBackend(ModelBackend):
    """
    Authenticate users using their email address instead of username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email", username)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None

        if user.check_password(password):
            return user
        return None

import logging
import os
import requests
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"

def send_otp_email(recipient_email: str, otp: str) -> bool:
    """Send OTP email through Brevo."""
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")
    sender_name = os.getenv("BREVO_SENDER_NAME", "Kauchy")
    subject = "Verify your email - Kauchy"

    if not api_key or not sender_email:
        logger.warning("Brevo OTP email not sent: missing BREVO_API_KEY or BREVO_SENDER_EMAIL")
        return False

    html_content = render_to_string(
        "account/otp_email.html",
        {
            "otp": otp,
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
        logger.exception("Brevo OTP email request failed: %s", exc)
        return False

    return True