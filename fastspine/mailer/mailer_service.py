from functools import lru_cache

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from ..services.base_service import BaseService
from ..settings import get_core_settings


class MailerService(BaseService):
    """Service class for managing mailer settings and operations."""

    @lru_cache()
    @staticmethod
    def _get_conf():
        """Get the mail configuration."""
        settings = get_core_settings()

        return ConnectionConfig(
            MAIL_USERNAME=MailerService._required(settings.MAIL_USERNAME, "MAIL_USERNAME"),
            MAIL_PASSWORD=MailerService._required(settings.MAIL_PASSWORD, "MAIL_PASSWORD"),
            MAIL_FROM=MailerService._required(settings.MAIL_FROM, "MAIL_FROM"),
            MAIL_PORT=MailerService._required(settings.MAIL_PORT, "MAIL_PORT"),
            MAIL_SERVER=MailerService._required(settings.MAIL_SERVER, "MAIL_SERVER"),
            MAIL_STARTTLS=MailerService._required(settings.MAIL_STARTTLS, "MAIL_STARTTLS"),
            MAIL_SSL_TLS=MailerService._required(settings.MAIL_SSL_TLS, "MAIL_SSL_TLS"),
            USE_CREDENTIALS=MailerService._required(settings.USE_CREDENTIALS, "USE_CREDENTIALS"),
            VALIDATE_CERTS=MailerService._required(settings.VALIDATE_CERTS, "VALIDATE_CERTS"),
        )

    @staticmethod
    def _required(value, name):
        if value is None:
            raise RuntimeError(f"Missing required mail setting: {name}")
        return value

    def get_fm(self):
        """Get the FastMail instance configured with the mail settings."""
        return FastMail(MailerService._get_conf())

    async def send_email(self, to: str, subject: str, body: str):
        """Send an email using the configured mailer settings."""
        message = MessageSchema(subject=subject, recipients=[to], body=body, subtype=MessageType.html)

        return await self.get_fm().send_message(message)
