# FastStack Examples

This directory contains working examples demonstrating FastStack's key features and patterns.

## Available Examples

### [Hello World](hello-world/) ⭐
**Minimal FastStack application demonstrating core concepts**
- Single model (Greeting)
- Repository pattern with BaseRepository
- Service layer with dependency injection
- Simple FastAPI endpoints
- **Technologies:** PostgreSQL, FastAPI
- **Complexity:** Beginner
- **Status:** ✅ Complete

---

## Planned Examples

The following examples are planned for future releases:

### Basic Blog API (Coming Soon)
**Simple blog application showcasing core FastStack patterns**
- User management with authentication
- Post creation and management
- Comment system
- Basic caching strategies
- **Technologies:** PostgreSQL, Redis, FastAPI
- **Complexity:** Beginner

### E-commerce Platform (Coming Soon)
**Production-like e-commerce system with advanced patterns**
- Multi-database architecture (Primary + Analytics)
- Advanced caching strategies
- Background task processing
- External API integrations
- **Technologies:** PostgreSQL, MongoDB, Redis, Celery
- **Complexity:** Advanced

### Analytics Dashboard (Coming Soon)
**Real-time analytics with heavy data processing**
- External database connections
- Complex SQL queries with AbstractRepository
- Real-time data processing
- Cache warming strategies
- **Technologies:** PostgreSQL, ClickHouse, Redis
- **Complexity:** Intermediate

## Hello World Example Overview

The [Hello World](hello-world/) example demonstrates FastStack fundamentals:

```python
from faststack import run_fast_core_app
from faststack.dependencies.database import register_sessions
from faststack.repositories.repository_manager import RepositoryManager
from sqlalchemy.orm import Session

# Session and Repository Manager
class SessionLocal(Session):
    pass

class LocalRepositoryManager(RepositoryManager[SessionLocal]):
    pass

# Register database
register_sessions([(SessionLocal, db_config)])

# Create app
app = run_fast_core_app()

# Repository (no __init__ needed!)
class GreetingRepository(BaseRepository[Greeting]):
    def get_latest(self, limit: int = 10):
        return self.db.query(self.model).limit(limit).all()

# Service with Repository Manager
class GreetingService(BaseService):
    def __init__(self,
        rm: LocalRepositoryManager = repository_manager_dep(LocalRepositoryManager)
    ):
        self.rm = rm

    def create_greeting(self, message: str):
        repo = self.rm.get(GreetingRepository)
        return repo.create(Greeting(message=message), commit=True)

# Endpoint using Service
@app.post("/greetings")
async def create_greeting(
    message: str,
    service: GreetingService = service_dep(GreetingService)
):
    return service.create_greeting(message)
```

## Running the Hello World Example

```bash
# Navigate to hello world example
cd docs/examples/hello-world

# Set up environment
uv init .  # or python -m venv venv && source venv/bin/activate

# Install dependencies
uv add faststack[all] uvicorn  # or pip install -r requirements.txt

# Start PostgreSQL (using Docker)
docker run --name hello-db \
  -e POSTGRES_DB=hello_world \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 -d postgres:15

# Run the application
uv run python main.py  # or python main.py
```

Visit `http://localhost:8000` and `http://localhost:8000/docs` for interactive API documentation.

## What You'll Learn from Hello World

- ✅ **Repository Pattern** - No `__init__` needed, session injected automatically
- ✅ **Repository Manager** - Type-safe database access per session
- ✅ **Service Layer** - Business logic with dependency injection
- ✅ **Automatic DI** - FastStack resolves all dependencies
- ✅ **Clean Architecture** - Separation of concerns

## Contributing Examples

We welcome community contributions of new examples! To contribute:

1. **Fork the repository**
2. **Create example directory** with clear name
3. **Include working code** with setup instructions
4. **Add comprehensive README.md**
5. **Test your example** thoroughly
6. **Submit pull request**

## Next Steps

After trying the Hello World example:

1. **[Getting Started Tutorial](../getting-started/hello-world.md)** - Step-by-step explanation
2. **[First App Tutorial](../getting-started/first-app.md)** - More complex multi-database example
3. **[Architecture Guide](../guides/architecture.md)** - Understanding FastStack internals
4. **[Dependency Injection Guide](../guides/dependency-injection.md)** - DI deep dive

## Getting Help

- 📖 **[Documentation](../README.md)** - Complete guides and API reference
- 💬 **[GitHub Discussions](https://github.com/your-username/faststack/discussions)** - Community help
- 🐛 **[Issues](https://github.com/your-username/faststack/issues)** - Bug reports and feature requests