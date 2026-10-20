class CelerySettings:
    """Settings class for Celery configuration."""

    CELERY_RESULT_EXPIRES: int = 7 * 24 * 60 * 60  # 7 days
    CELERY_BROKER_URI: str = ""
    CELERY_BACKEND_URI: str = "redis://localhost:6385/0"
    CELERY_MAIN_NAME: str = "_redis_main"
    CELERY_TASK_FOLDERS: list[str] = []
    WORKERS_ON: bool = True  # Whether workers are enabled
    VISIBILITY_TIMEOUT: int = 3600  # Default visibility timeout for tasks in seconds
