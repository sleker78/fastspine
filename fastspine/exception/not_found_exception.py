from .base_app_exception import BaseAppError


class NotFoundError(BaseAppError):
    """Exception raised for access denied errors.

    Attributes:
        STATUS_CODE -- HTTP status code for the error (default 404)
        DEFAULT_MESSAGE -- default error message
    """

    STATUS_CODE = 404
    DEFAULT_MESSAGE = "Rersource not found"
