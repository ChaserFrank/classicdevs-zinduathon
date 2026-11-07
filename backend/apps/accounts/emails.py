"""Account emails (verification, password reset). Plain text + HTML, rendered from templates.

Links point at the frontend (FRONTEND_URL), which posts the token back to the API. Sending happens
after the database commit and never fails the request: a mail outage must not block sign-up.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from . import tokens

logger = logging.getLogger(__name__)


def _send(template: str, user, context: dict) -> bool:
    context = {"user": user, "frontend_url": settings.FRONTEND_URL, **context}
    subject = render_to_string(f"accounts/email/{template}_subject.txt", context).strip()
    text = render_to_string(f"accounts/email/{template}.txt", context)
    html = render_to_string(f"accounts/email/{template}.html", context)
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html, "text/html")
    try:
        message.send()
    except Exception:
        logger.exception("Account email failed", extra={"template": template})
        return False
    return True


def send_verification_email(user) -> bool:
    link = f"{settings.FRONTEND_URL}/verify-email?token={tokens.make_email_token(user)}"
    return _send("verify_email", user, {"link": link})


def send_password_reset_email(user) -> bool:
    link = f"{settings.FRONTEND_URL}/reset-password?token={tokens.make_reset_token(user)}"
    return _send("password_reset", user, {"link": link})
