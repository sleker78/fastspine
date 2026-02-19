class BaseAppError(Exception):
    """Base class for all application exceptions."""

    def __init_subclass__(cls):
        """Ensure that all subclasses define STATUS_CODE and DEFAULT_MESSAGE."""
        super().__init_subclass__()
        if not hasattr(cls, "STATUS_CODE"):
            raise TypeError(f"{cls.__name__} must define STATUS_CODE constant")
        if not hasattr(cls, "DEFAULT_MESSAGE"):
            raise TypeError(f"{cls.__name__} must define DEFAULT_MESSAGE constant")

    def __init__(self, message=None, status_code=None):
        self.status_code = status_code or (self.__class__.STATUS_CODE if hasattr(self.__class__, "STATUS_CODE") else 500)
        self.message = message or (self.__class__.DEFAULT_MESSAGE if hasattr(self.__class__, "DEFAULT_MESSAGE") else "An error occurred")
        super().__init__(self.message)


class BaseError(Exception):
    """Base class for all application exceptions."""

    def __init__(self, detail, status_code=500):
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.detail)
