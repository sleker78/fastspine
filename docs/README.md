# FastStack Framework 🚀

**Enterprise-grade Python framework for production applications**

FastStack is a sophisticated, production-ready framework that combines the best of modern Python patterns with enterprise-level architecture. Built on top of FastAPI and SQLAlchemy, it provides advanced dependency injection, multi-database support, intelligent caching, and context-aware request management.

## ✨ Key Features

### 🧠 **Advanced Dependency Injection**
- **Runtime function generation** for dynamic database dependencies
- **Type-safe generic resolution** with automatic parameter extraction
- **Context-aware caching** with request-scoped lifecycle management
- **Unified DI patterns** across repositories, services, and managers

### 🗂️ **Multi-Layer Repository Architecture**
- **BaseRepository** - Full CRUD with soft delete awareness
- **AbstractRepository** - Raw SQL with security validation
- **ExternalRepository** - External database abstraction
- **RepositoryManager** - Centralized repository container

### 🗄️ **Intelligent Caching System**
- **Stampedo protection** with Redis locks
- **Multiple encoders** (JSON, Pickle) for flexible data types
- **Cache decorators** for methods and API responses
- **Automatic TTL management** with configurable expiration

### 🔄 **Advanced Task Management**
- **Task deduplication** with SHA256-based unique IDs
- **Automatic fallback functions** for error recovery
- **Database session integration** for Celery tasks
- **Context cleanup** with proper resource management

### 🗄️ **Multi-Database Support**
- **Per-database Repository Managers** with type-safe session isolation
- **4 database drivers** (PostgreSQL, MySQL, AsyncPG, AIOMySQL)
- **Cross-database service operations** with automatic DI
- **Connection pooling** with health checks
- **Dynamic session registration** at runtime

### 🧠 **Context Pool Management**
- **Centralized ContextVar management** (industry-first pattern)
- **Persistent vs temporary** context separation
- **Request-scoped state** with automatic cleanup
- **Cross-cutting concerns** handled elegantly

## 🚀 Quick Start

### Installation

```bash
uv add faststack  # Coming soon to PyPI
# or with pip
pip install faststack
```

### Multi-Database Usage

```python
from faststack import run_fast_stack_app
from faststack.dependencies.database import register_sessions
from faststack.database.engine import DBConfig
from faststack.repositories.repository_manager import RepositoryManager
from sqlalchemy.orm import Session

# Define Session classes for each database
class SessionApp(Session):
    """Session for main application DB."""
    pass

class SessionAnalytics(Session):
    """Session for analytics DB."""
    pass

# Define Repository Manager classes
class AppRepositoryManager(RepositoryManager[SessionApp]):
    """Repository manager for app DB operations."""
    pass

class AnalyticsRepositoryManager(RepositoryManager[SessionAnalytics]):
    """Repository manager for analytics DB operations."""
    pass

# Register multiple database sessions
register_sessions([
    (SessionApp, DBConfig(
        host="localhost", port=5432, dbname="myapp",
        user="postgres", password="password", service="postgres"
    )),
    (SessionAnalytics, DBConfig(
        host="analytics-db", port=5432, dbname="analytics",
        user="postgres", password="password", service="postgres"
    ))
])

# Create FastAPI app with FastStack
app = run_fast_stack_app()
```

### Service & Repository Example

```python
from faststack.repositories.base_repository import BaseRepository
from faststack.services.base_service import BaseService
from faststack.dependencies.repository_manager import repository_manager_dep
from faststack.dependencies.services import service_dep
from faststack.cache.cache_decorater import cache_method_async
from sqlalchemy.orm import Session
from faststack.lib.profiler import Profiler

# Repository (automatically gets session via Repository Manager)
class UserRepository(BaseRepository[User]):
    """User repository - NO __init__ needed, session injected automatically"""

    def find_by_email(self, email: str) -> User | None:
        return self.filter_one(email=email)

class AnalyticsRepository(BaseRepository[UserEvent]):
    """Analytics repository - NO __init__ needed, session injected automatically"""

    def track_user_action(self, user_id: int, action: str):
        event = UserEvent(user_id=user_id, action=action)
        return self.create(event, commit=True)

# Service (can use multiple Repository Managers)
class UserService(BaseService):
    def __init__(self,
        profiler: Profiler = Depends(get_profiler),
        app_rm: AppRepositoryManager = repository_manager_dep(AppRepositoryManager),
        analytics_rm: AnalyticsRepositoryManager = repository_manager_dep(AnalyticsRepositoryManager)
    ):
        super().__init__()
        self.profiler = profiler
        self.app_rm = app_rm
        self.analytics_rm = analytics_rm

    @cache_method_async(expire=300)
    async def get_user_with_analytics(self, user_id: int):
        # Access main app database
        user_repo = self.app_rm.get(UserRepository)
        user = user_repo.get_by_id(user_id)

        # Access analytics database
        analytics_repo = self.analytics_rm.get(AnalyticsRepository)
        analytics_repo.track_user_action(user_id, "profile_view")

        return user

# FastAPI endpoint using Service
@app.get("/users/{user_id}")
async def get_user(
    user_id: int,
    user_service: UserService = service_dep(UserService)
):
    return await user_service.get_user_with_analytics(user_id)
```

## 📚 Documentation Structure

### Getting Started
- **[Hello World](getting-started/hello-world.md)** - Simplest FastStack app in one file
- **[Installation](getting-started/installation.md)** - Setup and dependencies
- **[First App Tutorial](getting-started/first-app.md)** - Complete multi-database blog
- **[Configuration](getting-started/configuration.md)** - Advanced settings

### Guides
- **[Architecture Guide](guides/architecture.md)** - Framework design explained
- **[Dependency Injection](guides/dependency-injection.md)** - The magic behind the scenes
- **[Repositories](guides/repositories.md)** - Data access patterns
- **[Caching](guides/caching.md)** - Performance optimization
- **[API Reference](api/)** - Comprehensive API documentation
- **[Examples](examples/)** - Working code samples

## 🎯 Who Should Use FastStack?

### ✅ Perfect For:
- **Enterprise applications** requiring robust architecture
- **Multi-database applications** with complex data requirements
- **High-performance APIs** needing intelligent caching
- **Teams** wanting consistent, maintainable patterns
- **Background task systems** with Celery integration

### ⚠️ Consider Alternatives For:
- **Simple CRUD APIs** (FastAPI alone might suffice)
- **Prototype projects** (framework overhead might be excessive)
- **Small teams** unfamiliar with advanced Python patterns

## 🏆 Why FastStack?

| Feature | Django | FastAPI | Flask | **FastStack** |
|---------|--------|---------|-------|--------------|
| **Type Safety** | ❌ | ✅ | ❌ | **✅✅** |
| **Async Support** | ⚠️ | ✅ | ❌ | **✅✅** |
| **DI Container** | ❌ | ⚠️ | ❌ | **✅✅** |
| **Multi-DB** | ⚠️ | ❌ | ❌ | **✅✅** |
| **Enterprise Patterns** | ⚠️ | ❌ | ❌ | **✅✅** |
| **Context Management** | ❌ | ❌ | ❌ | **✅✅** |

## 🤝 Contributing

FastStack is designed for enterprise use and welcomes contributions that maintain its high standards:

- **Architecture discussions** - Propose improvements to core patterns
- **Performance optimizations** - Enhance existing systems
- **Documentation** - Help improve guides and examples
- **Testing** - Expand test coverage for edge cases

## 📄 License

MIT License - see [LICENSE](../LICENSE) for details.

## 🔗 Links

- **Documentation**: [docs/](.)
- **Examples**: [examples/](examples/)
- **Issues**: [GitHub Issues](https://github.com/your-username/faststack/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/faststack/discussions)

---

**Built with ❤️ for Python developers who demand excellence in enterprise applications.**