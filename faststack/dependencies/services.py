import inspect
from typing import Any

from fastapi import Depends

from ..ctx.ctx_pool import ctxpool
from ..dependencies.repository_manager import get_repository_manager, load_repository_manager
from ..repositories.repository_manager import RepositoryManager
from ..services.base_service import BaseService
from ..util.class_util import get_class_annotations

supported_params_type = [BaseService, RepositoryManager]
# Track dependency resolution to detect circular dependencies
_dependency_resolution_stack: set[type] = set()


def clear_cache():
    """Clear service cache."""
    ctxpool.clear_one("_service_cache_var")


def service_dep[SERVICE_T: BaseService](service_class: type[SERVICE_T]):
    """Create a dependency function for service. Used for DI inside Fastapi Depends lifecycle."""
    # Check for circular dependency
    if service_class in _dependency_resolution_stack:
        stack_names = [cls.__name__ for cls in _dependency_resolution_stack]
        raise ValueError(
            f"Circular dependency detected! Dependency chain: {' -> '.join(stack_names)} -> {service_class.__name__}"
        )

    _dependency_resolution_stack.add(service_class)

    try:
        annotations = get_class_annotations(service_class)

        # Build the signature dynamically based on service dependencies
        sig_params = []
        sig = inspect.signature(service_class.__init__)
        for param_name, param_type in annotations.items():
            if inspect.isclass(param_type) and issubclass(param_type, BaseService):
                # Nested service - create dependency
                nested_dep = service_dep(param_type)
                param = inspect.Parameter(
                    param_name, inspect.Parameter.KEYWORD_ONLY, default=Depends(nested_dep), annotation=param_type
                )
                sig_params.append(param)
            elif inspect.isclass(param_type) and issubclass(param_type, RepositoryManager):
                # Repository manager - use existing DI
                repo_factory = get_repository_manager(param_type)
                param = inspect.Parameter(
                    param_name, inspect.Parameter.KEYWORD_ONLY, default=Depends(repo_factory), annotation=param_type
                )
                sig_params.append(param)
            else:
                # For other parameters, check if they have defaults in the class __init__
                # If they do, skip them (let the class use its defaults)
                # If they don't, raise an error

                if param_name in sig.parameters and sig.parameters[param_name].default != inspect.Parameter.empty:
                    default_value = sig.parameters[param_name].default
                    if hasattr(default_value, "dependency"):
                        # This is a FastAPI dependency - preserve it in signature
                        param = inspect.Parameter(
                            param_name, inspect.Parameter.KEYWORD_ONLY, default=default_value, annotation=param_type
                        )
                        sig_params.append(param)
                    else:
                        # Parameter has other default value, skip it
                        continue
                else:
                    raise ValueError(
                        f"Unsupported dependency type {param_type} for parameter '{param_name}' in service {service_class.__name__}. "
                        f"Either provide a default value or use a supported type: {supported_params_type}"
                    )

        def factory(**kwargs) -> SERVICE_T:
            """Factory function to create the service instance."""
            dependecies = {}

            for param_name in annotations.keys():
                if param_name in kwargs:
                    # Dependency provided by FastAPI DI
                    dependecies[param_name] = kwargs[param_name]
                # For parameters with defaults, don't add them to dependencies
                # Let the class constructor use its default values
            return service_class(**dependecies)

        # Set the signature for FastAPI to understand
        factory.__signature__ = inspect.Signature(sig_params)  # type: ignore[attr-defined]

        return factory

    finally:
        # Always remove from stack when done
        _dependency_resolution_stack.discard(service_class)


def load_service[SERVICE_T: BaseService](service_class: type[SERVICE_T]) -> SERVICE_T:
    """Build a service instance outside FastAPI's DI, for use in CLI commands or other non-request contexts.

    Resolves constructor dependencies the same way `service_dep` does (nested BaseService or
    RepositoryManager parameters), but eagerly - via `load_service`/`load_repository_manager`
    instead of FastAPI's `Depends()`.
    """
    if service_class in _dependency_resolution_stack:
        stack_names = [cls.__name__ for cls in _dependency_resolution_stack]
        raise ValueError(
            f"Circular dependency detected! Dependency chain: {' -> '.join(stack_names)} -> {service_class.__name__}"
        )

    _dependency_resolution_stack.add(service_class)

    try:
        annotations = get_class_annotations(service_class)
        sig = inspect.signature(service_class.__init__)
        dependencies: dict[str, Any] = {}

        for param_name, param_type in annotations.items():
            if inspect.isclass(param_type) and issubclass(param_type, BaseService):
                dependencies[param_name] = load_service(param_type)
            elif inspect.isclass(param_type) and issubclass(param_type, RepositoryManager):
                dependencies[param_name] = load_repository_manager(param_type)
            elif param_name in sig.parameters and sig.parameters[param_name].default != inspect.Parameter.empty:
                # Parameter has its own default (e.g. a lazy property dependency) - let it be used.
                continue
            else:
                raise ValueError(
                    f"Unsupported dependency type {param_type} for parameter '{param_name}' in service {service_class.__name__}. "
                    f"Either provide a default value or use a supported type: {supported_params_type}"
                )

        return service_class(**dependencies)

    finally:
        _dependency_resolution_stack.discard(service_class)


def load_services(*service_classes: type[BaseService]) -> tuple[BaseService, ...]:
    """Load multiple services at once, outside FastAPI's DI, each via `load_service`."""
    return tuple(load_service(service_class) for service_class in service_classes)
