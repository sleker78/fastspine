import pytest

from faststack.dependencies.services import load_service, load_services, service_dep
from faststack.services.base_service import BaseService


class _ServiceWithDefault(BaseService):
    """A service whose only param has a plain (non-dependency) default."""

    def __init__(self, label: str = "default-label"):
        self.label = label


class _UnsupportedParamService(BaseService):
    """A service with a param that isn't `BaseService`/`RepositoryManager` and has no default."""

    def __init__(self, count: int):
        self.count = count


class _SelfReferentialService(BaseService):
    """A service that (incorrectly) depends on itself, to trigger circular-dependency detection."""

    def __init__(self, nested: "_SelfReferentialService"):
        self.nested = nested


def test_service_dep_factory_injects_the_repository_manager(sync_repo_manager_class):
    """`factory(**kwargs)` builds the service with whatever FastAPI would have injected."""

    class _Service(BaseService):
        def __init__(self, repo_manager: sync_repo_manager_class):  # type: ignore[valid-type]
            self.repo_manager = repo_manager

    factory = service_dep(_Service)
    fake_manager = sync_repo_manager_class(db=None)

    service = factory(repo_manager=fake_manager)

    assert isinstance(service, _Service)
    assert service.repo_manager is fake_manager


def test_service_dep_skips_params_with_a_plain_default():
    """A param with a plain default is left out of the built signature; the class's own default applies."""
    factory = service_dep(_ServiceWithDefault)

    service = factory()

    assert service.label == "default-label"


def test_service_dep_rejects_unsupported_param_types():
    """A param that's neither `BaseService`/`RepositoryManager` nor defaulted is rejected up front."""
    with pytest.raises(ValueError, match="Unsupported dependency type"):
        service_dep(_UnsupportedParamService)


def test_service_dep_detects_circular_dependencies():
    """A service depending on itself (directly or transitively) must fail fast, not recurse forever."""
    with pytest.raises(ValueError, match="Circular dependency detected"):
        service_dep(_SelfReferentialService)


def test_load_service_resolves_a_repository_manager_eagerly(sync_repo_manager_class):
    """`load_service` resolves `RepositoryManager` params via `load_repository_manager`."""

    class _Service(BaseService):
        def __init__(self, repo_manager: sync_repo_manager_class):  # type: ignore[valid-type]
            self.repo_manager = repo_manager

    service = load_service(_Service)

    assert isinstance(service.repo_manager, sync_repo_manager_class)


def test_load_service_resolves_nested_services(sync_repo_manager_class):
    """A nested `BaseService` dependency is resolved recursively, not just one level deep."""

    class _Inner(BaseService):
        def __init__(self, repo_manager: sync_repo_manager_class):  # type: ignore[valid-type]
            self.repo_manager = repo_manager

    class _Outer(BaseService):
        def __init__(self, inner: _Inner):
            self.inner = inner

    service = load_service(_Outer)

    assert isinstance(service.inner, _Inner)
    assert isinstance(service.inner.repo_manager, sync_repo_manager_class)


def test_load_service_skips_params_with_a_plain_default():
    """Same skip behavior as `service_dep`, but resolved eagerly instead of via `Depends()`."""
    service = load_service(_ServiceWithDefault)

    assert service.label == "default-label"


def test_load_service_rejects_unsupported_param_types():
    """`load_service` enforces the same supported-param-type rule as `service_dep`."""
    with pytest.raises(ValueError, match="Unsupported dependency type"):
        load_service(_UnsupportedParamService)


def test_load_service_detects_circular_dependencies():
    """`load_service` has its own circular-dependency guard, independent of `service_dep`'s."""
    with pytest.raises(ValueError, match="Circular dependency detected"):
        load_service(_SelfReferentialService)


def test_load_services_loads_each_service_independently():
    """`load_services` is a thin wrapper that loads every given service via `load_service`."""
    a, b = load_services(_ServiceWithDefault, _ServiceWithDefault)

    assert isinstance(a, _ServiceWithDefault)
    assert isinstance(b, _ServiceWithDefault)
