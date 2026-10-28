from typing import ClassVar

from celery import Celery
from pydantic_settings import BaseSettings

from ..settings import CoreSettings, get_core_settings, init_core_settings
from .broker import is_redis_broker


def get_celery_instance(settings: BaseSettings, *kwargs) -> Celery:
    """Get the Celery instance with the core settings."""
    core_settings: CoreSettings = init_core_settings(settings=settings)

    class Config:
        """Celery configuration class."""

        broker_transport_options: ClassVar = (
            {"visibility_timeout": core_settings.VISIBILITY_TIMEOUT}
            if is_redis_broker(core_settings.CELERY_BROKER_URI)
            else {}
        )

    return Celery(
        core_settings.CELERY_MAIN_NAME,
        broker=core_settings.CELERY_BROKER_URI,
        backend=core_settings.CELERY_BACKEND_URI,
        result_expires=core_settings.CELERY_RESULT_EXPIRES,
        broker_connection_retry_on_startup=False,
        config_source=Config,
        **kwargs,
    )


def run_celery_worker(settings: BaseSettings, argv=list[str]) -> Celery:
    """Run the Celery worker."""
    client = run_celery_client(settings)
    _autodiscover_tasks(client)
    client.worker_main(argv)

    return client


def run_celery_client(settings: BaseSettings) -> Celery:
    """Run the Celery client."""
    return get_celery_instance(settings)


def _autodiscover_tasks(celery_app: Celery, force: bool = False) -> None:
    """Autodiscover tasks in the specified folders.

    Args:
        celery_app (Celery, optional): The Celery app instance. Defaults to the global client.
        force (bool, optional): Whether to force the autodiscovery. Defaults to False.

    Created as wrapper for the original autodiscover_tasks function to allow for testing.
    """
    celery_app.autodiscover_tasks(get_core_settings().CELERY_TASK_FOLDERS, force=force)
