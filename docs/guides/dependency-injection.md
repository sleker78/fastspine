# Dependency Injection Guide

FastStack's dependency injection system is its most innovative feature, providing runtime function generation, type-safe resolution, and automatic dependency wiring. This guide explains how it works and how to use it effectively.

## How It Works

### Runtime Function Generation

FastStack generates dependency functions at runtime for multi-database setups:

```python
from faststack.dependencies.database import register_sessions
from sqlalchemy.orm import Session

# Define Session classes for each database
class SessionApp(Session):
    """Main application database session"""
    pass

class SessionAnalytics(Session):
    """Analytics database session"""
    pass

# Register multiple sessions at once
register_sessions([
    (SessionApp, app_db_config),
    (SessionAnalytics, analytics_db_config),
])

# This creates:
# - get_sessionapp_db() function for main database
# - get_sessionanalytics_db() function for analytics database

# Now you can use them in FastAPI
@app.get("/users")
async def get_users(db: SessionApp = Depends(get_sessionapp_db)):
    return db.query(User).all()

@app.get("/analytics/events")
async def get_events(db: SessionAnalytics = Depends(get_sessionanalytics_db)):
    return db.query(Event).all()
```

**What happens under the hood:**

```python
def register_sessions(sessions: List[Tuple[Type[Session], DBConfig]]):
    for session_cls, config in sessions:
        # 1. Create function name per database
        get_db_method_name = f"get_{session_cls.__name__.lower()}_db"

        # 2. Create the actual dependency function with specific config
        def generic_db_method():
            try:
                db_session, session_connection_pool, token = _load_db(session_cls)
                yield db_session  # FastAPI dependency yield pattern
            finally:
                _close_db(db_session, token, session_connection_pool)

        # 3. Add function to current module dynamically
        setattr(current_module, get_db_method_name, generic_db_method)

        # 4. Store mapping for Repository Manager resolution
        DB_MAPPING[session_cls] = generic_db_method
```

### Type Introspection Magic

FastStack automatically extracts type information from your classes:

```python
# Your repository
class UserRepository(BaseRepository[User]):
    def __init__(self, db: UserSession, profiler: Profiler):
        super().__init__(db, profiler)

# FastStack automatically knows:
# - Generic parameter T = User
# - Constructor parameter db: UserSession
# - Constructor parameter profiler: Profiler
```

The introspection works by examining Python's type system:

```python
def get_annotations(repo_class: Type, mandatory_params: list[str] = None) -> dict[str, Type]:
    """Extract type annotations from class constructor."""
    if hasattr(repo_class, "__init__"):
        signature = inspect.signature(repo_class.__init__)
        annotations = {}

        for param_name, param in signature.parameters.items():
            if param_name == "self":
                continue

            param_type = param.annotation
            if param_type != inspect.Parameter.empty:
                annotations[param_name] = param_type

        return annotations
```

## Dependency Resolution Chain

### Repository Manager Dependencies

FastStack uses Repository Managers to group repositories by database:

```python
from faststack.dependencies.repository_manager import repository_manager_dep
from faststack.repositories.repository_manager import RepositoryManager

# Define Repository Manager classes per database
class AppRepositoryManager(RepositoryManager[SessionApp]):
    """Repository manager for main application database"""
    pass

class AnalyticsRepositoryManager(RepositoryManager[SessionAnalytics]):
    """Repository manager for analytics database"""
    pass

# Service using multiple Repository Managers - CORRECT FastStack pattern
class UserService(BaseService):
    def __init__(self,
        profiler: Profiler = Depends(get_profiler),
        email_service: EmailService = Depends(),
        app_rm: AppRepositoryManager = repository_manager_dep(AppRepositoryManager),
        analytics_rm: AnalyticsRepositoryManager = repository_manager_dep(AnalyticsRepositoryManager)
    ):
        super().__init__()
        self.profiler = profiler
        self.email_service = email_service
        self.app_rm = app_rm
        self.analytics_rm = analytics_rm

    def create_user_with_analytics(self, user_data: dict):
        # Access main database via Repository Manager
        user_repo = self.app_rm.get(UserRepository)
        user = user_repo.create(User(**user_data))

        # Log to analytics database via different Repository Manager
        event_repo = self.analytics_rm.get(EventRepository)
        event_repo.log_event("user_created", {"user_id": user.id})

        # Send welcome email (other service dependency)
        self.email_service.send_welcome_email(user.email)

        return user

# FastAPI endpoint using Service
@app.post("/users")
async def create_user(
    user_data: UserCreateRequest,
    user_service: UserService = service_dep(UserService)
):
    return user_service.create_user_with_analytics(user_data.dict())
```

**Multi-Database Resolution Process:**

1. `repository_manager_dep(AppRepositoryManager)` extracts generic type `SessionApp`
2. Looks up `SessionApp` in `DB_MAPPING` → finds `get_sessionapp_db()`
3. Creates `AppRepositoryManager` instance with `SessionApp` dependency
4. Service receives both Repository Managers, each bound to different databases
5. Service can access repositories from multiple databases through `.get()` method

### Service Dependencies

```python
from faststack.dependencies.services import service_dep

class UserService(BaseService):
    def __init__(self, user_repo: UserRepository, email_service: EmailService):
        self.user_repo = user_repo
        self.email_service = email_service

# FastAPI endpoint
@app.post("/users")
async def create_user(
    user_data: UserCreateRequest,
    user_service: UserService = service_dep(UserService)
):
    return user_service.create_user(user_data)
```

**Service resolution supports:**
- Other services (recursive resolution)
- Repository managers
- Direct repositories
- Profiler instances

### Repository Manager Dependencies

```python
from faststack.dependencies.repository_manager import repository_manager_dep

class UserRepoManager(RepositoryManager[UserSession]):
    pass

@app.get("/dashboard")
async def get_dashboard(
    repo_manager: UserRepoManager = repository_manager_dep(UserRepoManager)
):
    user_repo = repo_manager.get(UserRepository)
    post_repo = repo_manager.get(PostRepository)
    # Multiple repositories with shared session
```

## Advanced Patterns

### Multiple Database Sessions

Register different session types for different purposes:

```python
# Define session classes
class PrimarySession(Session):
    """Main application database."""
    pass

class AnalyticsSession(Session):
    """Analytics and reporting database."""
    pass

class CacheSession(AsyncSession):
    """High-performance cache database."""
    pass

# Register with different configurations
from faststack.dependencies.database import register_sessions

register_sessions([
    (PrimarySession, primary_db_config),
    (AnalyticsSession, analytics_db_config),
    (CacheSession, async_cache_db_config),
])

# Use in repositories
class UserRepository(BaseRepository[User]):
    def __init__(self, db: PrimarySession, profiler: Profiler):
        super().__init__(db, profiler)

class EventRepository(AbstractRepository):
    def __init__(self, db: AnalyticsSession, profiler: Profiler):
        super().__init__(db, profiler)

class CacheRepository(AbstractRepository):
    def __init__(self, db: CacheSession, profiler: Profiler):
        super().__init__(db, profiler)
```

### Generic Repository Managers

Create specialized repository managers for different domains:

```python
class UserDomainManager(RepositoryManager[PrimarySession]):
    """Manages repositories for user-related operations."""

    def get_user_repo(self) -> UserRepository:
        return self.get(UserRepository)

    def get_profile_repo(self) -> ProfileRepository:
        return self.get(ProfileRepository)

class AnalyticsDomainManager(RepositoryManager[AnalyticsSession]):
    """Manages repositories for analytics operations."""

    def get_event_repo(self) -> EventRepository:
        return self.get(EventRepository)

    def get_metrics_repo(self) -> MetricsRepository:
        return self.get(MetricsRepository)
```

### Complex Service Dependencies

Services can depend on multiple repository managers and other services:

```python
class OrderService(BaseService):
    def __init__(
        self,
        user_manager: UserDomainManager,
        order_manager: OrderDomainManager,
        payment_service: PaymentService,
        notification_service: NotificationService,
        profiler: Profiler
    ):
        self.user_manager = user_manager
        self.order_manager = order_manager
        self.payment_service = payment_service
        self.notification_service = notification_service
        self.profiler = profiler

    async def process_order(self, order_data: OrderRequest) -> Order:
        with self.profiler.profile("process_order"):
            user_repo = self.user_manager.get_user_repo()
            order_repo = self.order_manager.get_order_repo()

            # Business logic using multiple dependencies
            user = user_repo.get_by_id(order_data.user_id)
            # ... complex order processing
```

### Background Task Dependencies

For Celery tasks and other background processes, use load functions instead of FastAPI dependencies:

```python
from faststack.dependencies.services import load_service
from faststack.dependencies.repositories import load_repository
from faststack.dependencies.repository_manager import load_repository_manager

from faststack.celery.base_task import BaseTask

class ProcessOrderTask(BaseTask):
    def run(self, order_id: int):
        # Load dependencies outside FastAPI context
        order_service = load_service(OrderService)
        user_repo = load_repository(UserRepository)
        order_manager = load_repository_manager(OrderDomainManager)

        # Process order
        return order_service.process_order_background(order_id)

# Register as Celery task
celery_app.register_task(ProcessOrderTask())
```

### Custom Dependency Factories

Create your own dependency patterns:

```python
from typing import TypeVar, Type, Callable
from fastapi import Depends

T = TypeVar('T')

def custom_service_dep(service_class: Type[T]) -> T:
    """Custom service dependency with additional setup."""

    def factory() -> T:
        # Custom initialization logic
        service = load_service(service_class)

        # Add custom setup
        service.setup_custom_context()

        return service

    return Depends(factory)

# Usage
@app.get("/custom")
async def custom_endpoint(
    service: CustomService = custom_service_dep(CustomService)
):
    return service.do_something()
```

## Context-Aware Dependencies

### Request Context Access

Dependencies can access the current request context:

```python
from faststack.ctx.ctx_pool import ctxpool

class AuditService(BaseService):
    def log_action(self, action: str, details: dict):
        # Get request context
        request = ctxpool.get("request_context")

        audit_log = {
            "action": action,
            "details": details,
            "correlation_id": getattr(request.state, "correlation_id", None),
            "user_agent": request.headers.get("user-agent"),
            "ip_address": request.client.host,
        }

        # Log to audit system
        self.audit_repo.create_audit_log(audit_log)
```

### Profiler Integration

The profiler is automatically injected and context-aware:

```python
class UserService(BaseService):
    def __init__(self, user_repo: UserRepository, profiler: Profiler):
        self.user_repo = user_repo
        self.profiler = profiler

    def expensive_operation(self, user_id: int):
        with self.profiler.profile("expensive_operation"):
            # Operation is automatically profiled
            # Results appear in request profiling data
            return self.complex_calculation(user_id)
```

## Performance Optimizations

### Request-Scoped Caching

Dependencies are cached per request to avoid repeated instantiation:

```python
# Each repository is created once per request
# Multiple dependencies can share the same instance

@app.get("/user-dashboard/{user_id}")
async def get_dashboard(
    user_id: int,
    user_service: UserService = service_dep(UserService),    # Creates UserRepository
    post_service: PostService = service_dep(PostService),    # Reuses UserRepository
):
    # Both services share the same UserRepository instance
    pass
```

### Session Pooling

Database sessions are pooled and reused within a request:

```python
class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo  # Gets session from pool

class PostService:
    def __init__(self, post_repo: PostRepository):
        self.post_repo = post_repo  # Gets SAME session from pool

# Both repositories share the same database session
# Commits and rollbacks affect both repositories
```

## Best Practices

### 1. Design Clear Interfaces

```python
# ✅ Good: Clear separation of concerns
class UserService(BaseService):
    def __init__(self, user_repo: UserRepository, email_service: EmailService):
        pass

# ❌ Avoid: Too many dependencies
class GodService(BaseService):
    def __init__(self, repo1, repo2, repo3, service1, service2, service3, ...):
        pass  # Too many dependencies = code smell
```

### 2. Use Repository Managers for Related Operations

```python
# ✅ Good: Group related repositories
class UserDomainManager(RepositoryManager[PrimarySession]):
    def get_user_repo(self) -> UserRepository:
        return self.get(UserRepository)

    def get_profile_repo(self) -> ProfileRepository:
        return self.get(ProfileRepository)

class UserService(BaseService):
    def __init__(self, user_domain: UserDomainManager):
        self.user_domain = user_domain
```

### 3. Type Safety Always

```python
# ✅ Good: Explicit types
class UserService(BaseService):
    def __init__(self, user_repo: UserRepository, profiler: Profiler):
        self.user_repo = user_repo
        self.profiler = profiler

# ❌ Avoid: No type hints
class UserService(BaseService):
    def __init__(self, user_repo, profiler):  # FastStack can't help you
        pass
```

### 4. Use Appropriate Dependency Level

```python
# For simple CRUD operations
user_repo: UserRepository = repository_dep(UserRepository)

# For business logic with multiple repositories
user_service: UserService = service_dep(UserService)

# For complex operations needing multiple repositories
user_manager: UserDomainManager = repository_manager_dep(UserDomainManager)
```

## Troubleshooting

### Common Issues

#### Missing Database Registration

```python
# Error: Unknown session class
user_repo: UserRepository = repository_dep(UserRepository)

# Solution: Register the session first
register_session(UserSession, db_config)
```

#### Type Resolution Errors

```python
# Error: Could not determine session type
class UserRepository(BaseRepository):  # Missing [User] generic
    def __init__(self, db, profiler):  # Missing type hints
        pass

# Solution: Add proper types
class UserRepository(BaseRepository[User]):
    def __init__(self, db: UserSession, profiler: Profiler):
        super().__init__(db, profiler)
```

#### Circular Dependencies

```python
# Error: Circular dependency
class ServiceA(BaseService):
    def __init__(self, service_b: ServiceB):
        pass

class ServiceB(BaseService):
    def __init__(self, service_a: ServiceA):
        pass

# Solution: Extract shared logic into a separate service or repository
class SharedRepository(BaseRepository[SharedModel]):
    pass

class ServiceA(BaseService):
    def __init__(self, shared_repo: SharedRepository):
        pass

class ServiceB(BaseService):
    def __init__(self, shared_repo: SharedRepository):
        pass
```

## Next Steps

- **[Repository Guide](repositories.md)** - Learn advanced repository patterns
- **[Service Architecture](services.md)** - Design effective service layers
- **[Testing DI Components](testing.md)** - Test dependency injection effectively
- **[Performance Tuning](performance.md)** - Optimize dependency resolution