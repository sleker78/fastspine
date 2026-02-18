# Caching in FastStack

FastStack provides a comprehensive Redis-based caching system with support for both synchronous and asynchronous operations, method caching, response caching, and model-based caching.

## Overview

The caching system consists of several components:

- **Redis Client** - Provides sync/async Redis connections
- **Cache Service** - High-level service for model caching operations
- **Cache Decorators** - Method and response caching decorators
- **Key Builder** - Generates cache keys from various inputs
- **Cache Encoders** - Handles serialization/deserialization
- **Cacheable Models** - Base class for cacheable data models

## Architecture

### Redis Backend

The system uses Redis as the caching backend, configured via:
- `WORKERS_ON` - Must be `True` to enable caching
- `CELERY_BROKER_URI` - Redis connection URL

### Key Components

#### 1. Redis Cache Module (`redis_cache.py`)
Low-level Redis operations with both sync and async support:

```python
from faststack.cache.redis_cache import cache_get, cache_set, cache_delete
from faststack.cache.redis_cache import cache_get_async, cache_set_async, cache_delete_async

# Synchronous operations
cache_set("my_key", {"data": "value"}, expire=300)
result = cache_get("my_key")

# Asynchronous operations
await cache_set_async("my_key", {"data": "value"}, expire=300)
result = await cache_get_async("my_key")
```

#### 2. Cache Service (`cache_service.py`)
High-level service for working with cacheable models:

```python
from faststack.cache.cache_service import CacheService

# Working with CachableModel instances
user = User(id=1, name="John")  # User extends CachableModel
CacheService.set(user)  # Cache the user
cached_user = CacheService.get("1", User)  # Retrieve from cache

# Async versions
await CacheService.aset(user)
cached_user = await CacheService.aget("1", User)

# Fetch with fallback
async def get_user_from_db():
    return User.from_database(1)

user = await CacheService.fetch_cache(user, get_user_from_db)
```

#### 3. Cacheable Models (`cache_model.py`)
Base class for models that can be cached:

```python
from faststack.cache.cache_model import CachableModel

class User(CachableModel):
    id: int
    name: str

    def get_cache_identifier(self) -> str:
        return str(self.id)

    def get_cache_expire_seconds(self) -> int:
        return 3600  # 1 hour
```

## Caching Decorators

### 1. Response Caching (`@cache_response`)
Caches FastAPI route responses based on request parameters:

```python
from faststack.cache.cache_decorater import cache_response

@app.get("/users/{user_id}")
@cache_response(expire=300, version="v1", key_prefix="users")
async def get_user(user_id: int):
    return {"id": user_id, "name": "John"}
```

Features:
- Only works with GET requests
- Automatically includes path and query parameters in cache key
- Supports cache bypass with `X-Cache-Bypass: true` header
- Uses Redis locks to prevent cache stampede

### 2. Method Caching (`@cache_method_async`, `@cache_method`)
Caches function results based on input parameters:

```python
from faststack.cache.cache_decorater import cache_method_async, cache_method

@cache_method_async(expire=600, version="v1")
async def expensive_calculation(x: int, y: int) -> int:
    # Expensive async operation
    return x * y

@cache_method(expire=300)
def sync_calculation(x: int) -> int:
    # Expensive sync operation
    return x ** 2
```

## Key Generation

The `KeyBuilder` class generates consistent cache keys:

```python
from faststack.cache.key_builder import KeyBuilder

# For functions
key = KeyBuilder.key_builder(func, namespace="api:v1", args=(1, 2), kwargs={"param": "value"})

# For requests
key = KeyBuilder.request_key_builder(func, version="v1", params={"id": 1})

# For models
user = User(id=1, name="John")
key = KeyBuilder.model_key_builder(user)

# Plain keys
key = KeyBuilder.model_plain_key_builder("User", "1")
```

All keys are automatically hashed using SHA256 for consistency.

## Encoders

The system supports different serialization strategies:

### PickledEncoder
For Python objects and complex data structures:
```python
from faststack.cache.cache_encoder import PickledEncoder

# Used internally by CacheService and method decorators
data = {"complex": object()}
encoded = PickledEncoder.encode(data)
decoded = PickledEncoder.decode(encoded)
```

### CacheResponseEncoder
For JSON-serializable data and Pydantic models:
```python
from faststack.cache.cache_encoder import CacheResponseEncoder

# Used by response caching decorator
response = {"id": 1, "name": "John"}
encoded = CacheResponseEncoder.encode(response)
decoded = CacheResponseEncoder.decode(encoded)
```

## Cache Patterns

### 1. Cache-Aside Pattern
Manually manage cache alongside data operations:

```python
async def get_user(user_id: int):
    # Try cache first
    cached = await cache_get_async(f"user:{user_id}")
    if cached:
        return cached

    # Fetch from database
    user = await db.get_user(user_id)

    # Update cache
    await cache_set_async(f"user:{user_id}", user, expire=3600)
    return user
```

### 2. Cache-Through Pattern with fetch_cache
Automatic cache management with fallback:

```python
user_model = User(id=user_id)
user = await CacheService.fetch_cache(user_model, lambda: fetch_from_db(user_id))
```

### 3. Write-Through Pattern
Update cache when data changes:

```python
async def update_user(user_id: int, data: dict):
    # Update database
    user = await db.update_user(user_id, data)

    # Update cache
    user_model = User(**user)
    await CacheService.aset(user_model)

    return user
```

## Locking and Race Conditions

The system includes Redis-based locking to prevent cache stampede:

```python
from faststack.cache.redis_cache import lock_async

async with lock_async("expensive_operation") as redis_lock:
    acquired = await redis_lock.acquire(blocking=True)
    if acquired:
        # Perform expensive operation
        result = await expensive_operation()
        await redis_lock.release()
```

## Configuration

Configure caching via environment settings:

```python
# Settings
WORKERS_ON = True  # Enable caching
CELERY_BROKER_URI = "redis://localhost:6379/0"  # Redis connection

# Usage in code
from faststack.settings import get_core_settings

settings = get_core_settings()
if settings.WORKERS_ON:
    # Caching is enabled
    pass
```

## Error Handling

Cache operations include comprehensive error handling:

```python
from faststack.cache.cache_exception import CacheError

try:
    result = await cache_get_async("my_key")
except CacheError as e:
    # Handle cache errors gracefully
    logger.error(f"Cache error: {e}")
    # Fallback to non-cached operation
```

## Best Practices

1. **Use appropriate expiration times** - Balance between performance and data freshness
2. **Handle cache misses gracefully** - Always have fallback logic
3. **Use model-based caching for entities** - Leverage `CachableModel` for consistent caching
4. **Monitor cache hit rates** - Track cache effectiveness
5. **Use locks for expensive operations** - Prevent cache stampede
6. **Choose appropriate encoders** - PickledEncoder for complex objects, CacheResponseEncoder for JSON data
7. **Version your cache keys** - Use version parameters when cache structure changes

## Sync vs Async Usage

### Use Sync Caching When:
- Working in **Celery tasks**
- Using synchronous business logic
- Operating in blocking contexts

### Use Async Caching When:
- Working in **FastAPI routes**
- Using async database operations
- Operating in async/await contexts

The system provides parallel APIs to support both patterns seamlessly.