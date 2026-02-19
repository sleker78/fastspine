# Configuration Guide

FastStack provides flexible configuration options for databases, caching, middleware, and more.

## Configuration Methods

### 1. Settings Classes (Recommended)

Use Pydantic settings for type-safe configuration:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings
from faststack.database.engine import DBConfig

class AppSettings(BaseSettings):
    # Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "myapp"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_SERVICE: str = "postgres"  # postgres, mysql, async_postgres, async_mysql

    # Cache Configuration
    CACHE_ENABLED: bool = True
    CACHE_KEY_PREFIX: str = "myapp"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery Configuration
    CELERY_BROKER_URI: str = "redis://localhost:6379/1"
    CELERY_BACKEND_URI: str = "redis://localhost:6379/2"
    CELERY_RESULT_EXPIRES: int = 3600
    CELERY_MAIN_NAME: str = "myapp.celery"
    CELERY_TASK_FOLDERS: list[str] = ["app.tasks"]

    # Application Configuration
    PROJECT_NAME: str = "My FastStack App"
    DEBUG_MODE: bool = False
    VISIBILITY_TIMEOUT: int = 300

    class Config:
        env_file = ".env"  # Load from environment file

    @property
    def db_config(self) -> DBConfig:
        return DBConfig(
            host=self.DB_HOST,
            port=self.DB_PORT,
            dbname=self.DB_NAME,
            user=self.DB_USER,
            password=self.DB_PASSWORD,
            service=self.DB_SERVICE
        )

@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()

settings = get_settings()
```

### 2. Environment Variables

Create a `.env` file:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=myapp
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_SERVICE=postgres

# Cache
CACHE_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URI=redis://localhost:6379/1
CELERY_BACKEND_URI=redis://localhost:6379/2

# Application
PROJECT_NAME="My Production App"
DEBUG_MODE=false
```

## Database Configuration

### Supported Databases

FastStack supports multiple database configurations:

#### PostgreSQL (Recommended)

```python
# Synchronous
db_config = DBConfig(
    host="localhost",
    port=5432,
    dbname="myapp",
    user="postgres",
    password="password",
    service="postgres"  # Uses psycopg2
)

# Asynchronous
db_config = DBConfig(
    host="localhost",
    port=5432,
    dbname="myapp",
    user="postgres",
    password="password",
    service="async_postgres"  # Uses asyncpg
)
```

#### MySQL

```python
# Synchronous
db_config = DBConfig(
    host="localhost",
    port=3306,
    dbname="myapp",
    user="mysql_user",
    password="password",
    service="mysql"  # Uses PyMySQL
)

# Asynchronous
db_config = DBConfig(
    host="localhost",
    port=3306,
    dbname="myapp",
    user="mysql_user",
    password="password",
    service="async_mysql"  # Uses aiomysql
)
```

### Multiple Databases

Register multiple database sessions:

```python
from faststack.dependencies.database import register_sessions
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

# Define custom session classes
class PrimarySession(Session):
    pass

class AnalyticsSession(Session):
    pass

class AsyncPrimarySession(AsyncSession):
    pass

# Register multiple databases
register_sessions([
    (PrimarySession, primary_db_config),
    (AnalyticsSession, analytics_db_config),
    (AsyncPrimarySession, async_primary_db_config),
])
```

Use in repositories:

```python
class UserRepository(BaseRepository[User]):
    def __init__(self, db: PrimarySession, profiler: Profiler):
        super().__init__(db, profiler)

class AnalyticsRepository(AbstractRepository):
    def __init__(self, db: AnalyticsSession, profiler: Profiler):
        super().__init__(db, profiler)
```

## Cache Configuration

### Redis Setup

```python
class CacheSettings(BaseSettings):
    CACHE_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str | None = None

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
```

### Cache Strategies

Configure different cache strategies:

```python
from faststack.cache.cache_decorater import cache_response, cache_method

# API Response Caching
@cache_response(expire=300, key_prefix="api", version="v1")
async def get_users():
    return user_service.get_all_users()

# Method Caching
@cache_method(expire=600, key_prefix="service", version="v2")
def expensive_calculation(self, param: int) -> dict:
    # Heavy computation
    return result

# Custom Cache Keys
@cache_response(
    expire=1800,
    exclude_params=["page", "limit"],  # Don't include in cache key
    version="v1"
)
async def search_posts(query: str, page: int = 1, limit: int = 10):
    return search_service.search(query, page, limit)
```

## Middleware Configuration

### Choose Middleware Type

```python
from faststack import run_fast_core_app

# BaseHTTPMiddleware (default)
app = run_fast_core_app(
    settings=settings,
    use_asgi_middleware=False
)

# Pure ASGI middleware (better performance)
app = run_fast_core_app(
    settings=settings,
    use_asgi_middleware=True
)
```

## Celery Configuration

### Basic Setup

```python
class CelerySettings(BaseSettings):
    CELERY_BROKER_URI: str = "redis://localhost:6379/1"
    CELERY_BACKEND_URI: str = "redis://localhost:6379/2"
    CELERY_RESULT_EXPIRES: int = 3600
    CELERY_MAIN_NAME: str = "myapp.celery"
    CELERY_TASK_FOLDERS: list[str] = ["app.tasks", "app.background"]
    VISIBILITY_TIMEOUT: int = 300

# Create Celery app
from faststack.celery.engine import get_celery_instance

celery_app = get_celery_instance(settings)
```

### Task Configuration

```python
from faststack.celery.base_task import BaseTask
from faststack.dependencies.services import load_services
from faststack.lib.contextualize import with_contextualize

@client.task(bind=True, model=BaseTask, acks_late=True, reject_on_worker_lost=True)
@with_contextualize(input_list_id="input_list_id")
def process_data_task(
    self,
    input_list_id: int,
    title: str,
    description: str,
    send_email: bool = True,
) -> bool:
    """Process data with FastStack services and proper error handling."""

    # Load multiple services with dependency injection
    data_service, email_service = load_services([
        DataProcessingService,
        EmailService
    ])

    # Get repository through service
    data_repo = data_service.rm.get(DataRepository)
    data_item = data_repo.get_instance(input_list_id)

    # Register task start
    data_service.register_worker_started(data_item=data_item)

    try:
        # Business logic here
        result = data_service.process_complex_data(
            title=title,
            description=description,
            data_item=data_item
        )

        # Register successful completion
        data_service.register_successful_finish(
            data_item=data_item,
            send_email=send_email
        )

        return True

    except Exception as e:
        # Log error with profiler
        data_service.profiler.error("Task failed", extra={"error": str(e)})
        raise


def process_data_task__fallback(input_list_id: int, *args, **kwargs) -> bool:
    """Fallback function executed if main task fails."""
    send_email = kwargs.get("send_email", False)

    # Load service for cleanup
    data_service = load_service(DataProcessingService)
    data_item = data_service.rm.get(DataRepository).get_instance(input_list_id)

    # Register failed finish
    data_service.register_failed_finish(
        data_item=data_item,
        send_email=send_email
    )

    return True
```

## Environment-Specific Configuration

### Development

```python
class DevelopmentSettings(AppSettings):
    DEBUG_MODE: bool = True
    DB_NAME: str = "myapp_dev"
    CACHE_KEY_PREFIX: str = "dev_myapp"

    class Config:
        env_file = ".env.dev"
```

### Production

```python
class ProductionSettings(AppSettings):
    DEBUG_MODE: bool = False
    DB_HOST: str = "prod-db.example.com"
    REDIS_URL: str = "redis://prod-redis.example.com:6379/0"

    # Security settings
    DB_PASSWORD: str = Field(..., min_length=12)  # Require strong password

    class Config:
        env_file = ".env.prod"
```

### Load Settings with Environment Variables

Simply use environment variables or different `.env` files:

```python
# Production: Set ENV_FILE environment variable
# export ENV_FILE=".env.prod"
#
# Or use different env files directly:
# settings = AppSettings(_env_file=".env.prod")

settings = get_settings()  # Uses .env by default
```

## Docker Configuration

### docker-compose.yml

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=production
      - DB_HOST=postgres
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  celery:
    build: .
    command: celery -A app.celery worker --loglevel=info
    environment:
      - ENVIRONMENT=production
      - DB_HOST=postgres
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
  redis_data:
```

## Best Practices

### 1. Security

- ✅ Use environment variables for secrets
- ✅ Validate configuration at startup
- ✅ Use strong passwords and secure connections
- ❌ Don't hardcode credentials in code

### 2. Performance

- ✅ Use connection pooling for databases
- ✅ Configure appropriate cache TTL values
- ✅ Choose ASGI middleware for high-throughput apps
- ✅ Tune Redis memory settings

### 3. Configuration
- ✅ Use `@lru_cache()` for settings instances
- ✅ Keep settings simple and focused
- ✅ Use environment variables for different environments
- ✅ Leverage Pydantic's built-in validation

## Next Steps

- **[Architecture Guide](../guides/architecture.md)** - Understand how configuration flows through the system
- **[Deployment Guide](../guides/deployment.md)** - Production deployment strategies
- **[Performance Tuning](../guides/performance.md)** - Optimize your configuration