class MailerSettings:
    """Settings class for mailer configuration."""

    MAIL_USERNAME: str | None = None
    MAIL_PASSWORD: str | None = None
    MAIL_FROM: str | None = None
    MAIL_PORT: int | None = None
    MAIL_SERVER: str | None = None
    MAIL_STARTTLS: bool | None = None
    MAIL_SSL_TLS: bool | None = None
    USE_CREDENTIALS: bool | None = None
    VALIDATE_CERTS: bool | None = None
