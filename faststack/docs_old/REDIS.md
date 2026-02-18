# Redis Client

This module provides both synchronous and asynchronous Redis clients for the FastStack application.

## Overview

The Redis client module offers two main functions:
- `get_redis_client()` - Returns a synchronous Redis client
- `get_async_redis_client()` - Returns an asynchronous Redis client

Both clients are initialized from the `CACHE_URI` configuration and require `CACHE_ENABLED` to be set to `True`.

## Usage

### Synchronous Redis Client

```python
from faststack.redis.client import get_redis_client

# Get the sync Redis client
redis_client = get_redis_client()

# Use in synchronous context (e.g., Celery tasks)
redis_client.set("key", "value")
value = redis_client.get("key")
```

### Asynchronous Redis Client

```python
from faststack.redis.client import get_async_redis_client

# Get the async Redis client
async_redis_client = get_async_redis_client()

# Use in asynchronous context (e.g., FastAPI endpoints)
await async_redis_client.set("key", "value")
value = await async_redis_client.get("key")
```

## Configuration

Both clients require the following settings:

- `WORKERS_ON` - Must be set to `True` to enable Redis functionality
- `CELERY_BROKER_URI` - Redis connection URL (e.g., `redis://localhost:6379/0`)

## When to Use Which Client

### Use Synchronous Client (`get_redis_client()`)
- In **Celery tasks** and other synchronous contexts
- When working with blocking operations
- In traditional Python scripts

### Use Asynchronous Client (`get_async_redis_client()`)
- In **FastAPI endpoints** and async request handlers
- When using async/await patterns
- In async middleware and dependencies

## Error Handling

Both functions will raise a `RuntimeError` if:
- `WORKERS_ON` is not set to `True`
- `CELERY_BROKER_URI` is not properly configured

## Caching

Both client functions use `@lru_cache` decorator to ensure singleton behavior - the same client instance is returned on subsequent calls.