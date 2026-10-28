from urllib.parse import urlparse

_REDIS_BROKER_SCHEMES = {"redis", "rediss"}


def is_redis_broker(broker_uri: str) -> bool:
    """Check whether a Celery broker URI points at Redis.

    Shared between `engine.py` (whether to pass Redis-specific `broker_transport_options`) and
    `base_task.py` (whether `BaseTask`'s own Redis-based deduplication should run at all - other
    brokers like RabbitMQ have their own message-deduplication module/plugin handling this at the
    transport level, so there's nothing for this app-level mechanism to add there, and no reason
    to require a working cache-Redis connection for it).
    """
    return urlparse(broker_uri).scheme in _REDIS_BROKER_SCHEMES
