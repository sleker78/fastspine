from .base_app_exception import BaseAppError


class ActionNotAllowedError(BaseAppError):
    """Exception raised for access denied errors.

    Attributes:
        STATUS_CODE -- HTTP status code for the error (default 403)
        DEFAULT_MESSAGE -- default error message
    """

    STATUS_CODE = 403
    DEFAULT_MESSAGE = "Action not allowed"
