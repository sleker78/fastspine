# Installation Guide

## Prerequisites

FastStack requires Python 3.10+ and is built on top of modern async frameworks.

### System Requirements

- **Python**: 3.10 or higher
- **Database**: PostgreSQL, MySQL, or compatible
- **Redis**: For caching and task queues (optional but recommended)
- **Memory**: Minimum 512MB RAM for development

## Installation Methods

### Method 1: uv (Recommended)

```bash
# Install FastStack with all dependencies using uv
uv add faststack

# Or install with specific database drivers
uv add faststack[postgres]     # PostgreSQL support
uv add faststack[mysql]        # MySQL support
uv add faststack[async]        # Full async support
uv add faststack[all]          # Everything included
```

### Method 2: pip (Alternative)

```bash
# Install FastStack with all dependencies
pip install faststack

# Or install with specific database drivers
pip install faststack[postgres]     # PostgreSQL support
pip install faststack[mysql]        # MySQL support
pip install faststack[async]        # Full async support
pip install faststack[all]          # Everything included
```

### Method 3: From Source

```bash
# Clone the repository
git clone https://github.com/your-username/faststack.git
cd faststack

# Using uv (recommended)
uv sync --all-extras

# Or using pip
pip install -e .[all]
```

## Database Drivers

FastStack supports multiple database configurations:

### PostgreSQL (Recommended)

```bash
# Using uv
uv add psycopg2-binary  # Synchronous
uv add asyncpg          # Asynchronous

# Using pip
pip install psycopg2-binary  # Synchronous
pip install asyncpg          # Asynchronous
```

### MySQL

```bash
# Using uv
uv add PyMySQL    # Synchronous
uv add aiomysql   # Asynchronous

# Using pip
pip install PyMySQL    # Synchronous
pip install aiomysql   # Asynchronous
```

## Optional Dependencies

### Redis (Highly Recommended)

```bash
# Using uv
uv add redis
uv add redis[hiredis]  # For async Redis operations

# Using pip
pip install redis
pip install redis[hiredis]  # For async Redis operations
```

### Celery (For Background Tasks)

```bash
# Using uv
uv add celery
uv add celery[redis]  # With Redis broker

# Using pip
pip install celery
pip install celery[redis]  # With Redis broker
```

### Development Tools

```bash
# Using uv (recommended)
uv add --dev pytest pytest-asyncio  # Testing
uv add --dev ruff mypy               # Code quality
uv add --dev mkdocs mkdocs-material  # Documentation

# Using pip
pip install pytest pytest-asyncio   # Testing
pip install ruff mypy                # Code quality
pip install mkdocs mkdocs-material   # Documentation
```

## Verification

Verify your installation by running:

```python
import faststack
print(f"FastStack version: {faststack.__version__}")

# Test database connectivity
from faststack.database.engine import DBConfig
config = DBConfig(
    host="localhost",
    port=5432,
    dbname="postgres",
    user="postgres",
    password="password"
)

# This should not raise any errors
engine = config.create_engine()
print("✅ Database connectivity test passed")
```

## Docker Setup (Recommended for Development)

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: faststack_dev
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

Start services:

```bash
docker-compose up -d
```

## Next Steps

Once installation is complete:

1. **[First App](first-app.md)** - Create your first FastStack application
2. **[Configuration](configuration.md)** - Configure databases and settings
3. **[Architecture Guide](../guides/architecture.md)** - Understand the framework structure

## Troubleshooting

### Common Issues

**ImportError: No module named 'faststack'**
```bash
# Check if FastStack is installed
uv list | grep faststack
# or
pip list | grep faststack
```

**Database Connection Errors**
```bash
# Check database is running
pg_isready -h localhost -p 5432

# Test connection manually
psql -h localhost -p 5432 -U postgres -d faststack_dev
```

**Redis Connection Issues**
```bash
# Test Redis connectivity
redis-cli ping
# Should return PONG
```

### Getting Help

- Check the [FAQ](../guides/faq.md)
- Review [common patterns](../examples/)
- Open an issue on [GitHub](https://github.com/your-username/faststack/issues)