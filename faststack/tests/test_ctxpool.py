import pytest

from ..ctx.ctx_pool import CtxPool


@pytest.fixture
def pool():
    """Fixture to create a new CtxPool instance for testing."""
    return CtxPool()


def test_new_and_get(pool):
    """Test creating a new context variable and retrieving its value."""
    pool.new("test_var", default=42)
    assert pool.get("test_var", 42) == 42


def test_set_and_get(pool):
    """Test setting a value for a context variable and retrieving it."""
    pool.new("my_var")
    pool.set("my_var", "hello")
    assert pool.get("my_var") == "hello"


def test_clear(pool):
    """Test clearing all context variables in the pool."""
    pool.new("a", default=1)
    pool.new("b", default=2, persistant=False)
    pool.set("a", 10)
    pool.set("b", 20)
    pool.clear()
    # "a" is persistent by default False, so cleared
    assert pool.get("a") is None
    assert pool.get("b") is None


def test_clear_one_non_persistent(pool):
    """Test clearing a specific non-persistent context variable."""
    pool.new("x", default=5)
    pool.set("x", 10)
    pool.clear_one("x")
    assert pool.get("x") is None


def test_clear_one_persistent_raises(pool):
    """Test that clearing a persistent context variable raises an error."""
    pool.new("p", default=7, persistant=True)
    pool.set("p", 10)
    with pytest.raises(ValueError):
        pool.clear_one("p")


def test_clear_one_not_found_raises(pool):
    """Test that clearing a non-existent context variable raises an error."""
    with pytest.raises(KeyError):
        pool.clear_one("nonexistent")


def test_set_not_found_raises(pool):
    """Test that setting a value for a non-existent context variable raises an error."""
    with pytest.raises(KeyError):
        pool.set("missing", 123)
