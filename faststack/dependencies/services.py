import contextvars
from typing import Callable, Type, TypeVar

from fastapi import Depends

from faststack.lib.profiler import Profiler

from ..ctx.ctx_pool import ctxpool
from ..dependencies.profiler import load_profiler
from ..dependencies.repositories import load_repository
from ..dependencies.repository_manager import load_repository_manager
from ..repositories.abstract_repository import AbstractRepository
from ..repositories.repository_manager import RepositoryManager
from ..services.base_service import BaseService
from ..util.class_util import get_annotations

SERVICE_T = TypeVar("SERVICE_T", bound=BaseService)
supported_params_type = [Profiler, AbstractRepository]
_service_cache_var: contextvars.ContextVar[dict] = ctxpool.new("_service_cache_var", default={})


def clear_cache():
    """Clear service cache."""
    ctxpool.clear_one("_service_cache_var")


def get_service(service_class: Type[SERVICE_T]) -> Callable[[], SERVICE_T]:
    """Get service instance for FastAPI. Relies on Depends in __init__."""
    return service_class


def load_service(service_class: Type[SERVICE_T]) -> SERVICE_T:
    """Load service.

    load_service is a utility function designed to create and return an instance of a service class. It is used for dependency injection (DI) in contexts where FastAPI's Depends mechanism is not available.
    """
    cache = ctxpool.get("service_cache", default={})

    if service_class in cache:
        return cache[service_class]
    annotations = get_annotations(service_class)
    dependencies = {}
    for param_name, param_type in annotations.items():
        if issubclass(param_type, RepositoryManager):
            dependencies[param_name] = load_repository_manager(param_type)
        elif issubclass(param_type, BaseService):
            dependencies[param_name] = load_service(param_type)
        elif issubclass(param_type, AbstractRepository):
            dependencies[param_name] = load_repository(param_type)
        elif param_type is Profiler:
            dependencies[param_name] = load_profiler()
    service_instance = service_class(**dependencies)
    new_cache = dict(cache)
    new_cache[service_class] = service_instance
    ctxpool.set("_service_cache_var", new_cache)

    return service_instance


def load_services(service_classes: list[Type[SERVICE_T]]) -> list[SERVICE_T]:
    """Load multiple services."""
    return [load_service(service_class) for service_class in service_classes]


def service_dep(service_class: Type[SERVICE_T]) -> SERVICE_T:
    """Service dependency."""
    return Depends(get_service(service_class))
