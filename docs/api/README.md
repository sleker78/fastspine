# FastStack API Reference

FastStack's API documentation is currently being built. This section will contain comprehensive API documentation for all FastStack components.

## Current Documentation Status

### ✅ Available Documentation
- **[Architecture Guide](../guides/architecture.md)** - How FastStack components work together
- **[Dependency Injection Guide](../guides/dependency-injection.md)** - DI system deep dive
- **[Repository Guide](../guides/repositories.md)** - Repository patterns and usage
- **[Caching Guide](../guides/caching.md)** - Caching strategies and implementation

### 🔄 Planned API Documentation

The following API documentation is planned for future releases:

#### Core Components
- **Dependencies** - Session registration, Repository Manager DI, Service DI
- **Context Management** - ContextVar pool, request-scoped context
- **Database** - Engine configuration, session management, multi-database setup
- **Repository Layer** - AbstractRepository, BaseRepository, Repository Manager
- **Service Layer** - BaseService, API services, factory patterns
- **Caching System** - Cache decorators, Redis integration, cache models
- **Celery Integration** - BaseTask, task patterns, engine configuration
- **Middleware** - Request/session middleware, ASGI vs BaseHTTP patterns
- **Models and Mixins** - BaseModel, soft delete, pagination
- **Utilities** - Type introspection, profiling, debugging

## Auto-Generated Documentation

API documentation will be generated from docstrings using tools like:

- **[Sphinx](https://www.sphinx-doc.org/)** with autodoc
- **[MkDocs](https://www.mkdocs.org/)** with mkdocstrings
- **[pdoc](https://pdoc.dev/)** for simple generation

## Temporary API Reference

Until comprehensive API docs are ready, explore the source code with these key modules:

## Quick Reference

### Common Import Patterns

```python
# Main application setup
from faststack import run_fast_core_app

# Database registration
from faststack.dependencies.database import register_sessions
from faststack.database.engine import DBConfig

# Repository Manager dependency injection
from faststack.dependencies.repository_manager import repository_manager_dep
from faststack.repositories.repository_manager import RepositoryManager

# Service dependency injection
from faststack.dependencies.services import service_dep

# Repository base classes
from faststack.repositories.base_repository import BaseRepository
from faststack.repositories.abstract_repository import AbstractRepository

# Service base class
from faststack.services.base_service import BaseService

# Caching decorators
from faststack.cache.cache_decorater import cache_response, cache_method_async, cache_method

# Models and mixins
from faststack.models.base import BaseModel
from faststack.mixins import SoftDeleteMixin

# Profiler
from faststack.lib.profiler import Profiler

# Context management
from faststack.ctx.ctx_pool import ctxpool

# Celery tasks (if using background tasks)
from faststack.celery.base_task import BaseTask

# Pagination schemas
from faststack.schemas.pagination_model import PaginationParams, PaginatedList
```

### Type Definitions & Usage Patterns

```python
from typing import TypeVar
from sqlalchemy.orm import Session
from faststack.lib.profiler import Profiler
from faststack.models.base import BaseModel
from faststack.repositories.base_repository import BaseRepository
from faststack.repositories.repository_manager import RepositoryManager

# Common TypeVars (used internally by FastStack)
T = TypeVar('T', bound=BaseModel)
SESSION_T = TypeVar('SESSION_T', bound=Session)

# Repository (NO __init__ needed - session injected automatically)
class MyRepository(BaseRepository[MyModel]):
    """Repository for MyModel - session injected via Repository Manager"""

    def find_by_name(self, name: str) -> MyModel | None:
        return self.filter_one(name=name)

# Repository Manager (bound to specific Session type)
class MySessionManager(RepositoryManager[MySession]):
    """Repository Manager for specific database session"""
    pass

# Session definition
class MySession(Session):
    """Custom session class for specific database"""
    pass
```

## Current Resources

While comprehensive API documentation is being developed, use these resources:

### 📖 **Available Now**
- **[Getting Started](../getting-started/)** - Setup and basic usage
- **[Architecture Guide](../guides/architecture.md)** - How components work together
- **[Dependency Injection](../guides/dependency-injection.md)** - DI system explained
- **[Hello World Example](../examples/hello-world/)** - Working code example

### 🔧 **For Developers**
- **Source code** - Well-documented with type hints and docstrings
- **Examples** - Working applications demonstrating patterns
- **Tests** - Unit and integration tests showing usage

## Contributing API Documentation

Help us build comprehensive API docs! We follow these standards:

- **Google-style docstrings** with type hints
- **Working examples** for complex methods
- **Exception documentation** where relevant
- **Cross-references** to related components

## Next Steps

1. **Try [Hello World](../examples/hello-world/)** - See FastStack in action
2. **Read [Architecture Guide](../guides/architecture.md)** - Understand the design
3. **Explore source code** - Discover advanced features
4. **Contribute documentation** - Help improve the docs!