from .base_app_exception import BaseAppError


class SecurityAlertError(BaseAppError):
    """Exception raised for security alerts.

    Attributes:
        STATUS_CODE -- HTTP status code for the exception
        DEFAULT_MESSAGE -- default message for the exception
    """

    STATUS_CODE = 403
    DEFAULT_MESSAGE = " Unauthorized attempt detected. Access logged!"
