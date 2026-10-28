import pytest

from fastspine.celery.broker import is_redis_broker


@pytest.mark.parametrize(
    ("broker_uri", "expected"),
    [
        ("redis://localhost:6379/0", True),
        ("rediss://localhost:6379/0", True),
        ("amqp://guest@localhost//", False),
        ("kafka://localhost:9092", False),
        ("", False),
    ],
)
def test_is_redis_broker(broker_uri, expected):
    """Only redis:// and rediss:// broker URIs count as a Redis broker."""
    assert is_redis_broker(broker_uri) is expected
