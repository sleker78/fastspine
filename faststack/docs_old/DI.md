# Dependency Injection (DI)

Dependency Injection (DI) is a design pattern that helps manage dependencies in a clean and modular way. Instead of creating dependencies directly within a class or function, they are provided (injected) from an external source. This approach promotes:

- **Loose Coupling:** Reduces direct dependencies between components, making the code more flexible and easier to modify.
- **Testability:** Simplifies unit testing by allowing mock dependencies to be injected.
- **Maintainability:** Encourages separation of concerns and makes the codebase easier to understand and maintain.

## How DI Works in FastAPI

In FastAPI, DI is implemented using Python's type hints and the `Depends` function. It allows you to inject shared resources like database connections, services, or configurations into your route handlers or other components.

### Example

```python
from fastapi import FastAPI, Depends

app = FastAPI()

# Dependency function
def get_config():
    return {"key": "value"}

@app.get("/")
def read_root(config: dict = Depends(get_config)):
    return {"config": config}
```

The `Depends` dependency injection mechanism, commonly used in FastAPI, is not available in the Celery task lifecycle.

## FastStack DI

### Service Injection in FastStack

FastStack provides a lightweight and flexible mechanism for service injection, enabling you to manage dependencies effectively within your application. This approach simplifies the integration of services and promotes cleaner, more maintainable code.

To ensure that services are injectable in FastStack, every service should extend the `faststack.dependencies.services.BaseService` class. This base class provides the necessary structure and functionality for dependency injection.

When you need to inject a service directly into a route, you can use the `faststack.load_service_dep` utility. This allows you to seamlessly integrate services into your application without manually managing their lifecycle.

### Example

```python
from faststack.dependencies.services import BaseService
from faststack import load_service_dep
from fastapi import FastAPI


# Define a service
class MyService(BaseService):
    def get_message(self):
        return "Hello from MyService!"

# Inject the service into a route
@app.get("/")
def read_root(service: MyService = load_service_dep(MyService)):
    return {"message": service.get_message()}
```

By following this pattern, you can maintain a clean and modular architecture while leveraging the power of dependency injection in FastStack.

### Repository Injection in FastStack

FastStack also supports repository injection, enabling you to manage data access layers in a clean and modular way. Repositories are responsible for encapsulating the logic required to access data sources, such as databases or APIs.

To ensure that repositories are injectable in FastStack, every repository should extend the `faststack.dependencies.repositories.BaseRepository` class. This base class provides the necessary structure and functionality for dependency injection.

When you need to inject a repository directly into a route, you can use the `faststack.load_repository_dep` utility, similar to service injection. This allows you to seamlessly integrate repositories into your application without manually managing their lifecycle.

### Example

```python
from faststack.dependencies.repositories import BaseRepository
from faststack import load_service_dep
from fastapi import FastAPI

# Define a repository
class MyRepository(BaseRepository[MySqlAlchemyModel]):
    """MyRepository repository."""

    def __init__(self, db: SessionLocal):
        super().__init__(db, profiler)

    def get_data(self):
        return {"data": "Sample data from MyRepository"}

# Inject the repository into a route
@app.get("/data")
def read_data(repository: MyRepository = load_repository_dep(MyRepository)):
    return repository.get_data()
```

By adopting this pattern, you can maintain a clear separation of concerns between your application's business logic and data access layers, resulting in a more maintainable and testable codebase.

To inject a repository into a service class, you can follow the same dependency injection principles described earlier. This approach allows the service class to depend on the repository for data access, promoting a clean separation of concerns between the service's business logic and the repository's data access logic.

Here's how you can achieve this:

1. Define the Repository: The repository encapsulates the logic for accessing data sources.
2. Define the Service: The service class depends on the repository and uses it to perform business logic.
3. Inject the Repository into the Service: Use the load_repository_dep utility to inject the repository into the service class.

## Repository Manager

FastStack provides a `RepositoryManager` class that simplifies the management of multiple repositories within a single database session. The Repository Manager acts as a central hub for accessing different repositories while maintaining a shared database session and providing transaction management capabilities.

### Key Features

- **Centralized Repository Management**: Manages multiple repository instances with a single database session
- **Lazy Loading**: Repository instances are created only when first accessed
- **Transaction Management**: Provides methods for commit, rollback, and flush operations
- **Both Sync and Async Support**: Works with both synchronous and asynchronous database sessions
- **Dependency Injection Support**: Can be injected into services and routes

### Basic Usage

```python
from faststack.repositories.repository_manager import RepositoryManager
from sqlalchemy.orm import Session

# Create a repository manager
db_session = get_database_session()
repo_manager = RepositoryManager[Session](db_session)

# Access repositories through the manager
user_repo = repo_manager.get(UserRepository)
order_repo = repo_manager.get(OrderRepository)

# Perform operations
user = user_repo.create({"name": "John", "email": "john@example.com"})
order = order_repo.create({"user_id": user.id, "total": 100.0})

# Commit all changes in a single transaction
repo_manager.commit()
```

### Async Usage

```python
from sqlalchemy.ext.asyncio import AsyncSession

# Create async repository manager
async_db_session = get_async_database_session()
repo_manager = RepositoryManager[AsyncSession](async_db_session)

# Access repositories
user_repo = repo_manager.get(AsyncUserRepository)

# Perform async operations
user = await user_repo.acreate({"name": "Jane"})

# Commit asynchronously
await repo_manager.acommit()
```

### Transaction Management

The Repository Manager provides comprehensive transaction management:

```python
try:
    # Get repositories
    user_repo = repo_manager.get(UserRepository)
    audit_repo = repo_manager.get(AuditRepository)

    # Perform multiple operations
    user = user_repo.create(user_data)
    repo_manager.flush()  # Flush to get user.id

    audit_repo.create({"action": "user_created", "user_id": user.id})

    # Commit all changes
    repo_manager.commit()

except Exception as e:
    # Rollback on error
    repo_manager.rollback()
    raise
```

### Dependency Injection with Repository Manager

#### In FastAPI Routes

```python
from faststack.dependencies.repository_manager import repository_manager_dep

class MyRepositoryManager(RepositoryManager[Session]):
    pass

@app.post("/users")
def create_user(
    user_data: UserCreateModel,
    repo_manager: MyRepositoryManager = repository_manager_dep(MyRepositoryManager)
):
    user_repo = repo_manager.get(UserRepository)
    audit_repo = repo_manager.get(AuditRepository)

    try:
        user = user_repo.create(user_data.dict())
        audit_repo.log_action("user_created", user.id)
        repo_manager.commit()
        return user
    except Exception:
        repo_manager.rollback()
        raise
```

#### In Celery Tasks (Non-FastAPI Context)

```python
from faststack.dependencies.repository_manager import load_repository_manager

@celery_app.task
def process_user_data(user_id: int):
    # Load repository manager outside FastAPI context
    repo_manager = load_repository_manager(MyRepositoryManager)

    user_repo = repo_manager.get(UserRepository)
    analytics_repo = repo_manager.get(AnalyticsRepository)

    try:
        user = user_repo.get(user_id)
        analytics_repo.track_event("user_processed", user.id)
        repo_manager.commit()
    except Exception:
        repo_manager.rollback()
        raise
```

### Repository Manager Methods

#### Session Management
- `commit()` / `acommit()` - Commit the current transaction
- `rollback()` / `arollback()` - Rollback the current transaction
- `flush()` / `aflush()` - Flush pending changes without committing
- `read_commit()` / `aread_commit()` - Commit read-only transactions (validates no changes exist)

#### Repository Management
- `get(repository_class)` - Get or create a repository instance

### Benefits of Using Repository Manager

1. **Shared Transaction Scope**: All repositories share the same database session and transaction
2. **Simplified Transaction Management**: Single point to commit, rollback, or flush changes
3. **Lazy Loading**: Repository instances are created only when needed
4. **Type Safety**: Full type hints and IDE support
5. **Consistent Session Handling**: Ensures all repositories use the same session instance
6. **Memory Efficient**: Repositories are cached and reused within the same manager instance

### Best Practices

1. **Use Repository Manager for Multi-Repository Operations**: When you need to work with multiple repositories in a single transaction
2. **Handle Transactions Properly**: Always commit or rollback transactions appropriately
3. **Use Read Commits for Read-Only Operations**: Use `read_commit()` when you only perform read operations
4. **Leverage Dependency Injection**: Use `repository_manager_dep()` in FastAPI and `load_repository_manager()` in Celery
5. **Keep Repository Logic Separate**: Repository Manager handles session management, not business logic








