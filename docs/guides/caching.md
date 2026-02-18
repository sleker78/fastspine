# Caching Strategies Guide

FastStack provides a comprehensive caching system with Redis integration, multiple encoders, stampedo protection, and flexible decorators. This guide covers all caching patterns and optimization strategies.

## Caching Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    FastStack Cache System                  │
├─────────────────┬─────────────────┬─────────────────────────┤
│   Decorators    │    Encoders     │       Storage           │
├─────────────────┼─────────────────┼─────────────────────────┤
│ @cache_response │ JSON Encoder    │ Redis Primary           │
│ @cache_method   │ Pickle Encoder  │ Redis Cluster           │
│ @cache_async    │ Custom Encoder  │ Memory (Dev)            │
├─────────────────┼─────────────────┼─────────────────────────┤
│        Stampedo Protection + TTL Management                │
└─────────────────────────────────────────────────────────────┘
```

## Cache Decorators

### API Response Caching

Cache HTTP responses with automatic key generation based on request parameters:

```python
from faststack.cache.cache_decorater import cache_response

@app.get("/users")
@cache_response(expire=300, version="v1", key_prefix="api")
async def get_users(
    page: int = 1,
    limit: int = 20,
    search: str = None
):
    # Only executed if not in cache
    return user_service.get_paginated_users(page, limit, search)

@app.get("/user/{user_id}/posts")
@cache_response(
    expire=600,                           # 10 minutes
    exclude_params=["page", "limit"],     # Don't include pagination in cache key
    version="v2",
    key_prefix="user_posts"
)
async def get_user_posts(
    user_id: int,
    page: int = 1,
    limit: int = 10,
    include_deleted: bool = False
):
    # Cache key includes user_id and include_deleted, but not page/limit
    return post_service.get_user_posts(user_id, page, limit, include_deleted)
```

### Service Method Caching

Cache expensive service operations:

```python
from faststack.cache.cache_decorater import cache_method_async, cache_method

class UserService(BaseService):
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    @cache_method_async(expire=1800, key_prefix="user_service", version="v1")
    async def get_user_statistics(self, user_id: int) -> dict:
        """Cache user statistics for 30 minutes."""
        # Expensive calculation
        posts_count = self.user_repo.count_user_posts(user_id)
        avg_engagement = self.user_repo.calculate_avg_engagement(user_id)
        follower_count = self.user_repo.count_followers(user_id)

        return {
            "posts_count": posts_count,
            "avg_engagement": avg_engagement,
            "follower_count": follower_count,
            "calculated_at": datetime.utcnow()
        }

    @cache_method(expire=3600, key_prefix="user_service", version="v1")
    def get_user_recommendations(self, user_id: int) -> list[dict]:
        """Cache recommendations for 1 hour."""
        # Complex recommendation algorithm
        return self.recommendation_engine.calculate_recommendations(user_id)

class AnalyticsService(BaseService):
    @cache_method_async(expire=7200, key_prefix="analytics", version="v1")
    async def generate_monthly_report(self, month: int, year: int) -> dict:
        """Cache monthly reports for 2 hours."""
        # Heavy data processing
        data = self.analytics_repo.get_monthly_data(month, year)
        return self.process_analytics_data(data)
```

### Cache Bypass and Invalidation

```python
@app.get("/users/{user_id}")
@cache_response(expire=600, version="v1")
async def get_user(
    user_id: int,
    request: Request
):
    # Bypass cache with header
    if request.headers.get("X-Cache-Bypass") == "true":
        # Will refresh cache with new data
        pass

    return user_service.get_user_by_id(user_id)

class UserService(BaseService):
    def update_user(self, user_id: int, user_data: dict) -> User:
        """Update user and invalidate related caches."""
        user = self.user_repo.update_user(user_id, user_data)

        # Invalidate user-specific caches
        self.invalidate_user_caches(user_id)

        return user

    def invalidate_user_caches(self, user_id: int):
        """Invalidate all caches related to a user."""
        cache_keys = [
            f"user_service:get_user_statistics:{user_id}",
            f"user_service:get_user_recommendations:{user_id}",
            f"api:get_user:{user_id}"
        ]

        for key in cache_keys:
            cache_delete(KeyBuilder.hash_key(key))
```

## Cache Service Pattern

Use the `CacheService` for model-based caching:

```python
from faststack.cache.cache_service import CacheService
from faststack.cache.cache_model import CachableModel

class UserProfileCache(CachableModel):
    """Cacheable user profile model."""
    user_id: int
    email: str
    full_name: str
    avatar_url: str | None = None
    last_active: datetime

    def get_cache_identifier(self) -> str:
        return str(self.user_id)

    def get_cache_expire_seconds(self) -> int:
        return 1800  # 30 minutes

class UserService(BaseService):
    async def get_user_profile_cached(self, user_id: int) -> UserProfileCache:
        """Get user profile with model-based caching."""
        cache_key = UserProfileCache(user_id=user_id)

        # Try to get from cache first
        cached_profile = await CacheService.aget(str(user_id), UserProfileCache)
        if cached_profile:
            return cached_profile

        # Fetch and cache if not found
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        profile = UserProfileCache(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            last_active=user.last_active_at
        )

        # Cache the profile
        await CacheService.aset(profile)
        return profile

    async def get_or_compute_profile(self, user_id: int) -> UserProfileCache:
        """Use fetch_cache for automatic cache-aside pattern."""
        cache_model = UserProfileCache(user_id=user_id)

        async def profile_provider() -> UserProfileCache:
            user = self.user_repo.get_by_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")

            return UserProfileCache(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                avatar_url=user.avatar_url,
                last_active=user.last_active_at
            )

        # Automatic cache-aside with stampedo protection
        return await CacheService.fetch_cache(
            cache_model,
            profile_provider,
            expiration=1800
        )
```

## Advanced Caching Patterns

### Multi-Level Caching

Combine different cache levels for optimal performance:

```python
class ProductService(BaseService):
    def __init__(self, product_repo: ProductRepository):
        self.product_repo = product_repo
        self._memory_cache = {}  # Simple in-memory cache

    async def get_product(self, product_id: int) -> Product:
        """Multi-level cache: Memory → Redis → Database."""

        # Level 1: Memory cache (fastest)
        if product_id in self._memory_cache:
            cached_at = self._memory_cache[product_id]["cached_at"]
            if datetime.utcnow() - cached_at < timedelta(minutes=5):
                return self._memory_cache[product_id]["product"]

        # Level 2: Redis cache
        cached_product = await cache_get_async(
            f"product:{product_id}",
            PickledEncoder
        )
        if cached_product:
            # Store in memory cache
            self._memory_cache[product_id] = {
                "product": cached_product,
                "cached_at": datetime.utcnow()
            }
            return cached_product

        # Level 3: Database
        product = self.product_repo.get_by_id(product_id)
        if not product:
            raise ValueError(f"Product {product_id} not found")

        # Cache in both levels
        await cache_set_async(
            f"product:{product_id}",
            product,
            expire=3600,  # 1 hour in Redis
            encoder=PickledEncoder
        )

        self._memory_cache[product_id] = {
            "product": product,
            "cached_at": datetime.utcnow()
        }

        return product
```

### Cache Warming

Pre-populate caches for better performance:

```python
class CacheWarmingService(BaseService):
    def __init__(
        self,
        user_service: UserService,
        product_service: ProductService,
        analytics_service: AnalyticsService
    ):
        self.user_service = user_service
        self.product_service = product_service
        self.analytics_service = analytics_service

    async def warm_popular_data(self):
        """Warm cache with popular data."""

        # Warm popular user profiles
        popular_user_ids = await self.get_popular_user_ids()
        for user_id in popular_user_ids:
            try:
                await self.user_service.get_user_statistics(user_id)
                await self.user_service.get_user_recommendations(user_id)
            except Exception as e:
                logger.warning(f"Failed to warm cache for user {user_id}: {e}")

        # Warm popular products
        popular_product_ids = await self.get_popular_product_ids()
        for product_id in popular_product_ids:
            try:
                await self.product_service.get_product(product_id)
            except Exception as e:
                logger.warning(f"Failed to warm cache for product {product_id}: {e}")

    async def warm_daily_reports(self):
        """Pre-generate daily reports."""
        today = date.today()

        # Generate last 7 days of reports
        for days_ago in range(7):
            report_date = today - timedelta(days=days_ago)
            try:
                await self.analytics_service.generate_daily_report(
                    report_date.day,
                    report_date.month,
                    report_date.year
                )
            except Exception as e:
                logger.warning(f"Failed to warm daily report for {report_date}: {e}")

# Schedule cache warming
from celery.schedules import crontab

@celery_app.task
def warm_cache_task():
    """Celery task to warm cache."""
    warming_service = load_service(CacheWarmingService)
    asyncio.run(warming_service.warm_popular_data())

# Run every hour
celery_app.conf.beat_schedule = {
    'warm-cache': {
        'task': 'warm_cache_task',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

### Cache Tags and Invalidation

Implement cache tagging for grouped invalidation:

```python
class TaggedCacheService:
    """Cache service with tagging support."""

    @staticmethod
    async def set_with_tags(key: str, value: Any, expire: int, tags: list[str]):
        """Set cache value with tags."""
        # Store the actual value
        await cache_set_async(key, value, expire)

        # Store tag mappings
        for tag in tags:
            tag_key = f"tag:{tag}"
            # Add key to tag's key set
            redis_client = get_async_redis_client()
            await redis_client.sadd(tag_key, key)
            await redis_client.expire(tag_key, expire + 3600)  # Tags live longer

    @staticmethod
    async def invalidate_by_tag(tag: str):
        """Invalidate all cache entries with a specific tag."""
        redis_client = get_async_redis_client()
        tag_key = f"tag:{tag}"

        # Get all keys with this tag
        keys = await redis_client.smembers(tag_key)

        if keys:
            # Delete all tagged keys
            await redis_client.delete(*keys)
            # Delete the tag key itself
            await redis_client.delete(tag_key)

class UserService(BaseService):
    @cache_method_async(expire=1800)
    async def get_user_dashboard(self, user_id: int) -> dict:
        """Get user dashboard with tagging."""
        dashboard_data = await self.calculate_dashboard_data(user_id)

        # Cache with tags for easy invalidation
        cache_key = f"user:dashboard:{user_id}"
        await TaggedCacheService.set_with_tags(
            cache_key,
            dashboard_data,
            expire=1800,
            tags=[f"user:{user_id}", "dashboard", "user_data"]
        )

        return dashboard_data

    async def invalidate_user_data(self, user_id: int):
        """Invalidate all cache entries for a user."""
        await TaggedCacheService.invalidate_by_tag(f"user:{user_id}")
```

## Cache Configuration Strategies

### Environment-Based Configuration

```python
from pydantic_settings import BaseSettings

class CacheSettings(BaseSettings):
    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None
    REDIS_SSL: bool = False

    # Cache Behavior
    DEFAULT_CACHE_TTL: int = 3600
    MAX_CACHE_TTL: int = 86400  # 24 hours
    CACHE_KEY_PREFIX: str = "faststack"

    # Performance Settings
    CACHE_COMPRESSION: bool = False
    CACHE_SERIALIZER: str = "pickle"  # or "json"

    # Development Settings
    CACHE_ENABLED: bool = True
    CACHE_DEBUG: bool = False

    class Config:
        env_file = ".env"

# Environment-specific settings
class DevelopmentCacheSettings(CacheSettings):
    CACHE_DEBUG: bool = True
    DEFAULT_CACHE_TTL: int = 60  # Short TTL for development

class ProductionCacheSettings(CacheSettings):
    REDIS_SSL: bool = True
    CACHE_COMPRESSION: bool = True
    DEFAULT_CACHE_TTL: int = 3600
```

### Cache Partitioning

Separate caches by concern:

```python
class CacheManager:
    """Manages different cache namespaces."""

    def __init__(self):
        self.session_cache = self._create_redis_client(db=0)  # User sessions
        self.data_cache = self._create_redis_client(db=1)     # Application data
        self.temp_cache = self._create_redis_client(db=2)     # Temporary data

    def _create_redis_client(self, db: int):
        return redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=db,
            password=settings.REDIS_PASSWORD
        )

    async def cache_user_session(self, session_id: str, data: dict, expire: int = 3600):
        """Cache user session data."""
        await self.session_cache.setex(f"session:{session_id}", expire, pickle.dumps(data))

    async def cache_api_response(self, key: str, data: Any, expire: int = 1800):
        """Cache API response data."""
        await self.data_cache.setex(f"api:{key}", expire, pickle.dumps(data))

    async def cache_computation_result(self, key: str, result: Any, expire: int = 300):
        """Cache temporary computation results."""
        await self.temp_cache.setex(f"temp:{key}", expire, pickle.dumps(result))
```

## Performance Optimization

### Efficient Key Design

```python
class CacheKeyBuilder:
    """Efficient cache key generation."""

    @staticmethod
    def user_profile_key(user_id: int) -> str:
        return f"user:profile:{user_id}"

    @staticmethod
    def user_posts_key(user_id: int, page: int = 1, include_deleted: bool = False) -> str:
        deleted_suffix = ":deleted" if include_deleted else ""
        return f"user:posts:{user_id}:page:{page}{deleted_suffix}"

    @staticmethod
    def search_results_key(query: str, filters: dict) -> str:
        # Normalize query and filters for consistent keys
        normalized_query = query.lower().strip()
        filter_hash = hashlib.md5(json.dumps(filters, sort_keys=True).encode()).hexdigest()
        return f"search:{normalized_query}:{filter_hash}"

    @staticmethod
    def analytics_key(metric: str, date_range: tuple, dimensions: dict) -> str:
        start_date, end_date = date_range
        dimension_hash = hashlib.md5(json.dumps(dimensions, sort_keys=True).encode()).hexdigest()
        return f"analytics:{metric}:{start_date}:{end_date}:{dimension_hash}"
```

### Batch Operations

```python
class BatchCacheOperations:
    """Efficient batch cache operations."""

    @staticmethod
    async def get_multiple_users(user_ids: list[int]) -> dict[int, User]:
        """Get multiple users with single Redis call."""
        keys = [f"user:{user_id}" for user_id in user_ids]

        redis_client = get_async_redis_client()
        cached_values = await redis_client.mget(keys)

        results = {}
        missing_ids = []

        for i, (user_id, cached_value) in enumerate(zip(user_ids, cached_values)):
            if cached_value:
                results[user_id] = pickle.loads(cached_value)
            else:
                missing_ids.append(user_id)

        # Fetch missing users from database
        if missing_ids:
            user_repo = load_repository(UserRepository)
            missing_users = user_repo.filter_by(User.id.in_(missing_ids))

            # Cache missing users
            cache_operations = {}
            for user in missing_users:
                cache_operations[f"user:{user.id}"] = pickle.dumps(user)
                results[user.id] = user

            if cache_operations:
                await redis_client.mset(cache_operations)
                # Set expiration for all keys
                for key in cache_operations.keys():
                    await redis_client.expire(key, 3600)

        return results

    @staticmethod
    async def invalidate_multiple(keys: list[str]):
        """Invalidate multiple cache keys efficiently."""
        if not keys:
            return

        redis_client = get_async_redis_client()
        await redis_client.delete(*keys)
```

## Monitoring and Debugging

### Cache Metrics

```python
class CacheMetrics:
    """Cache performance monitoring."""

    def __init__(self):
        self.hit_count = 0
        self.miss_count = 0
        self.error_count = 0

    @property
    def hit_rate(self) -> float:
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0

    def record_hit(self):
        self.hit_count += 1

    def record_miss(self):
        self.miss_count += 1

    def record_error(self):
        self.error_count += 1

    def get_stats(self) -> dict:
        return {
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "error_count": self.error_count,
            "hit_rate": self.hit_rate,
            "total_requests": self.hit_count + self.miss_count
        }

# Global metrics instance
cache_metrics = CacheMetrics()

# Enhanced cache decorator with metrics
def cache_with_metrics(expire: int = 3600, key_prefix: str = "cache"):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = KeyBuilder.key_builder(func, f"{key_prefix}:metrics", args=args, kwargs=kwargs)

            try:
                # Try cache first
                cached_result = await cache_get_async(cache_key, PickledEncoder)
                if cached_result is not None:
                    cache_metrics.record_hit()
                    return cached_result

                # Cache miss
                cache_metrics.record_miss()

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                await cache_set_async(cache_key, result, expire, PickledEncoder)

                return result

            except Exception as e:
                cache_metrics.record_error()
                logger.error(f"Cache error for key {cache_key}: {e}")
                # Fall back to function execution
                return await func(*args, **kwargs)

        return wrapper
    return decorator
```

### Cache Debugging

```python
class CacheDebugger:
    """Cache debugging utilities."""

    @staticmethod
    async def inspect_cache_key(key: str) -> dict:
        """Inspect cache key details."""
        redis_client = get_async_redis_client()

        exists = await redis_client.exists(key)
        if not exists:
            return {"exists": False}

        ttl = await redis_client.ttl(key)
        value_size = await redis_client.memory_usage(key)
        value_type = await redis_client.type(key)

        return {
            "exists": True,
            "ttl": ttl,
            "size_bytes": value_size,
            "type": value_type.decode(),
            "key": key
        }

    @staticmethod
    async def list_keys_by_pattern(pattern: str) -> list[dict]:
        """List cache keys matching pattern."""
        redis_client = get_async_redis_client()
        keys = await redis_client.keys(pattern)

        results = []
        for key in keys:
            key_info = await CacheDebugger.inspect_cache_key(key.decode())
            results.append(key_info)

        return results

    @staticmethod
    async def cache_health_check() -> dict:
        """Check cache system health."""
        redis_client = get_async_redis_client()

        try:
            # Test basic operations
            test_key = "health_check"
            await redis_client.set(test_key, "ok", ex=60)
            value = await redis_client.get(test_key)
            await redis_client.delete(test_key)

            # Get Redis info
            info = await redis_client.info()

            return {
                "status": "healthy",
                "redis_version": info.get("redis_version"),
                "used_memory": info.get("used_memory_human"),
                "connected_clients": info.get("connected_clients"),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "hit_rate": info.get("keyspace_hits", 0) / max(
                    info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1
                )
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# Debug endpoint
@app.get("/debug/cache/{key:path}")
async def debug_cache_key(key: str):
    """Debug endpoint for cache inspection."""
    return await CacheDebugger.inspect_cache_key(key)

@app.get("/debug/cache-health")
async def cache_health():
    """Cache health check endpoint."""
    return await CacheDebugger.cache_health_check()
```

## Best Practices

### 1. Choose Appropriate TTL Values

```python
# ✅ Good TTL strategy
USER_PROFILE_TTL = 1800      # 30 minutes - changes occasionally
PRODUCT_CATALOG_TTL = 3600   # 1 hour - stable data
SEARCH_RESULTS_TTL = 300     # 5 minutes - dynamic data
ANALYTICS_TTL = 7200         # 2 hours - expensive calculations

# ❌ Avoid fixed TTL for everything
EVERYTHING_TTL = 3600  # Too rigid
```

### 2. Handle Cache Failures Gracefully

```python
async def get_user_with_fallback(user_id: int) -> User:
    """Get user with cache fallback."""
    try:
        # Try cache first
        cached_user = await cache_get_async(f"user:{user_id}", PickledEncoder)
        if cached_user:
            return cached_user
    except Exception as e:
        logger.warning(f"Cache error for user {user_id}: {e}")
        # Continue to database fallback

    # Database fallback
    user = user_repo.get_by_id(user_id)
    if user:
        try:
            # Try to cache for next time
            await cache_set_async(f"user:{user_id}", user, 1800, PickledEncoder)
        except Exception as e:
            logger.warning(f"Failed to cache user {user_id}: {e}")

    return user
```

### 3. Use Appropriate Encoding

```python
# ✅ Use JSON encoder for simple API responses
@cache_response(expire=300, encoder="json")
async def get_simple_data():
    return {"message": "hello", "count": 42}

# ✅ Use Pickle encoder for complex objects
@cache_method(expire=1800, encoder="pickle")
def get_complex_objects(self) -> list[ComplexModel]:
    return [ComplexModel(...) for _ in range(100)]
```

### 4. Implement Cache Warming

```python
# ✅ Warm critical caches during deployment
async def warm_critical_caches():
    """Warm up critical application caches."""
    critical_user_ids = [1, 2, 3, 4, 5]  # VIP users
    critical_product_ids = [10, 20, 30]   # Popular products

    tasks = []
    for user_id in critical_user_ids:
        tasks.append(user_service.get_user_statistics(user_id))

    for product_id in critical_product_ids:
        tasks.append(product_service.get_product_details(product_id))

    await asyncio.gather(*tasks, return_exceptions=True)
```

## Next Steps

- **[Performance Tuning](performance.md)** - Optimize cache performance
- **[Monitoring Guide](monitoring.md)** - Monitor cache metrics
- **[Testing Strategies](testing.md)** - Test cached components
- **[Production Deployment](deployment.md)** - Deploy with caching