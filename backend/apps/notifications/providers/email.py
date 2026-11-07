"""Email through Django's mail framework (Mailpit in dev, any SMTP in production).

If the organisers provide a Thrivewave email API, add another class with the same `send` method.
"""

from dataclasses import dataclass
from typing import Protocol

from django.conf import settings
from django.core.mail import EmailMultiAlternatives


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    text: str
    html: str


class EmailProvider(Protocol):
    name: str

    def send(self, message: EmailMessage) -> str | None:
        """Send or raise. Returns a provider message id when the provider gives one."""


class SmtpEmailProvider:
    name = "smtp"

    def send(self, message: EmailMessage) -> str | None:
        mail = EmailMultiAlternatives(
            message.subject, message.text, settings.DEFAULT_FROM_EMAIL, [message.to]
        )
        mail.attach_alternative(message.html, "text/html")
        mail.send()
        return mail.extra_headers.get("Message-ID")


def get_email_provider() -> EmailProvider:
    return SmtpEmailProvider()
