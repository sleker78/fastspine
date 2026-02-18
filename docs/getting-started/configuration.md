# Configuration Guide

FastStack provides flexible configuration options for databases, caching, middleware, and more.

## Configuration Methods

### 1. Settings Classes (Recommended)

Use Pydantic settings for type-safe configuration:

```python
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

settings = AppSettings()
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

class MyTask(BaseTask):
    def run(self, *args, **kwargs):
        # Your task logic
        return "Task completed"

# Fallback function (optional)
def my_task__fallback(*args, **kwargs):
    # Executed if MyTask fails
    logger.error("Task failed, executing fallback")

# Register task
celery_app.register_task(MyTask())
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

### Load Environment-Specific Settings

```python
import os
from typing import Type

def get_settings() -> Type[AppSettings]:
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        return ProductionSettings()
    elif env == "staging":
        return StagingSettings()
    else:
        return DevelopmentSettings()

settings = get_settings()
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

## Configuration Validation

### Custom Validators

```python
from pydantic import validator
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    DB_PASSWORD: str
    REDIS_URL: str

    @validator('DB_PASSWORD')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v

    @validator('REDIS_URL')
    def validate_redis_url(cls, v):
        if not v.startswith(('redis://', 'rediss://')):
            raise ValueError('Invalid Redis URL format')
        return v

    def validate_config(self):
        """Custom validation logic."""
        if self.CACHE_ENABLED and not self.REDIS_URL:
            raise ValueError("Redis URL required when cache is enabled")
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

### 3. Monitoring

```python
class MonitoringSettings(BaseSettings):
    # Profiler settings
    PROFILER_ENABLED: bool = True
    PROFILER_SAMPLE_RATE: float = 0.1

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Metrics
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
```

## Next Steps

- **[Architecture Guide](../guides/architecture.md)** - Understand how configuration flows through the system
- **[Deployment Guide](../guides/deployment.md)** - Production deployment strategies
- **[Performance Tuning](../guides/performance.md)** - Optimize your configuration