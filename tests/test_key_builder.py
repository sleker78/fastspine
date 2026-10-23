from faststack.cache.key_builder import KeyBuilder


def _handler():
    pass


def test_request_key_builder_is_sensitive_to_key_prefix():
    """Regression test: `key_prefix` used to be silently ignored (duplicated `version` instead)."""
    key_a = KeyBuilder.request_key_builder(_handler, version="v1", key_prefix="a", params={})
    key_b = KeyBuilder.request_key_builder(_handler, version="v1", key_prefix="b", params={})

    assert key_a != key_b


def test_request_key_builder_is_sensitive_to_version():
    """Bumping `version` must invalidate previously cached keys for the same handler/params."""
    key_v1 = KeyBuilder.request_key_builder(_handler, version="v1", key_prefix="cache", params={})
    key_v2 = KeyBuilder.request_key_builder(_handler, version="v2", key_prefix="cache", params={})

    assert key_v1 != key_v2


def test_request_key_builder_is_deterministic():
    """The same inputs must always produce the same key."""
    key_1 = KeyBuilder.request_key_builder(_handler, version="v1", key_prefix="cache", params={"a": 1})
    key_2 = KeyBuilder.request_key_builder(_handler, version="v1", key_prefix="cache", params={"a": 1})

    assert key_1 == key_2


def test_key_builder_is_sensitive_to_namespace():
    """`namespace` (built from `key_prefix:version` by the decorators) must affect the key."""
    key_a = KeyBuilder.key_builder(_handler, namespace="cache:v1", args=(), kwargs={})
    key_b = KeyBuilder.key_builder(_handler, namespace="cache:v2", args=(), kwargs={})

    assert key_a != key_b


def test_key_builder_is_sensitive_to_args_and_kwargs():
    """Different call arguments must produce different cache keys."""
    key_a = KeyBuilder.key_builder(_handler, namespace="cache:v1", args=(1,), kwargs={})
    key_b = KeyBuilder.key_builder(_handler, namespace="cache:v1", args=(2,), kwargs={})

    assert key_a != key_b


class _Service:
    def method(self, x):
        pass


def test_key_builder_strips_self_for_bound_methods_but_not_a_real_arg():
    """Regression test for a check that stripped every first arg, not just `self`.

    The old `hasattr(args[0], "__class__")` check stripped every first arg, since almost everything
    has a `__class__` - not just `self`. The key must only drop `self` for an actual method
    (detected from the function's own signature), and must still distinguish calls with a
    different real argument.
    """
    instance = _Service()

    # Same `self`, different real arg -> different keys (the real arg must not be the one dropped).
    key_x1 = KeyBuilder.key_builder(_Service.method, namespace="cache:v1", args=(instance, 1), kwargs={})
    key_x2 = KeyBuilder.key_builder(_Service.method, namespace="cache:v1", args=(instance, 2), kwargs={})
    assert key_x1 != key_x2

    # Different `self`, same real arg -> same key (self correctly dropped for a method).
    other_instance = _Service()
    key_other = KeyBuilder.key_builder(_Service.method, namespace="cache:v1", args=(other_instance, 1), kwargs={})
    assert key_x1 == key_other
