# FastStack + FastAPI Usage Guide

## How to install faststack?

```bash
uv add faststack
```

## FastAPI Usage

1. **Define Settings class** with required properties.

```python
class Settings(BaseSettings):
    """Settings class for application settings and secrets management.

    Official documentation on pydantic settings management:
    - https://pydantic-docs.helpmanual.io/usage/settings/
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # App specific settings
    DEBUG_MODE: bool = True
    PROJECT_NAME: str = "project name"
    APP_SECRET: str = "change-me-in-production--for-dev-only-aaaaa="  # noqa S105
    PUBLIC_URL: str = "http://localhost:8079/"
    ...
@lru_cache()
def get_settings() -> Settings:
    """Get the application settings with caching.

    Returns:
        Settings: The application settings instance.
    """
    return Settings()
```

2. **Instead of common FastAPI call (`app = FastAPI(...)`), use:**

```python
app = run_fast_core_app(get_settings())
```

**!! IMPORTANT:**  
`get_settings` is outside the scope of faststack lib but is defined as best practice for FastAPI:

```python
from functools import lru_cache

@lru_cache
def get_settings():
    """Get the settings instance."""
    return Settings()
```

3. **Define sessions, repository managers and register them:**

```python
from faststack import RepositoryManager
from faststack.dependencies.database import register_sessions
from sqlalchemy.orm import Session
from cfpbackend.src.config import get_settings

# Define Session classes for each database
class SessionLocal(Session):
    """Session for APP DB."""
    pass

class SessionMdpi(Session):
    """Session for MDPI DB."""
    pass

class SessionDwh(Session):
    """Session for DWH DB."""
    pass

# Define Repository Manager classes for each database
class RepositoryManagerLocal(RepositoryManager[SessionLocal]):
    """Repository manager for APP DB operations."""
    pass

class RepositoryManagerMdpi(RepositoryManager[SessionMdpi]):
    """Repository manager for MDPI DB operations."""
    pass

class RepositoryManagerDwh(RepositoryManager[SessionDwh]):
    """Repository manager for DWH DB operations."""
    pass

# Register sessions
register_sessions(
    [
        (SessionLocal, get_settings().APP_DB_CONFIG),
        (SessionMdpi, get_settings().MDPI_DB_CONFIG),
        (SessionDwh, get_settings().DWH_DB_CONFIG),
    ]
)
```

**Notes:**
- For async version use **from sqlalchemy.ext.asyncio import AsyncSession**
- Define a **Session class for each database** (currently MySQL and Postgres are supported).
- Define a **Repository Manager class for each database** - these will be used in services for coordinated operations.
- `register_sessions` is mandatory and you need to provide the class with **required parameters for DB connection**.
- Example DBConfig structure:

```json
{
    "host": "localhost",
    "port": 5497,
    "user": "app",
    "password": "supersecret",
    "dbname": "cfpassistant",
    "service": "postgres"
}
```

After this, sessions are available for further usage.

4. **Define repository**  

Every repository should be related to one entity/model:

```python
from faststack import BaseRepository
from faststack.lib.profiler import Profiler
from cfpbackend.src.models.database import Task
from cfpbackend.src.session import SessionLocal

class TaskRepository(BaseRepository[Task]):
    """Task repository."""
    pass
```

After this, repository methods are available: `get_by_id`, `delete`, `commit`, `filter_by`, `filter_one`, `create`, `fetch_all`, `fetch_one`.

5. **Services**

Keep your business logic inside services by injecting repository classes.
Every service must inherit:

```python
from faststack.services.base_service import BaseService
```

### Option A: Service with Individual Repository

Repository can be injected into service using `repository_dep`:

```python
from fastapi import Depends
from faststack.dependencies.repositories import repository_dep
from faststack.services.base_service import BaseService
from cfpbackend.src.repositories.task_repository import TaskRepository
from faststack.lib.profiler import Profiler

class TaskService(BaseService):
    """Service for task-related operations using individual repository."""

    def __init__(
        self,
        profiler: Profiler = Depends(get_profiler),
        repo: TaskRepository = repository_dep(TaskRepository)
    ):
        self.repo = repo

    def create_task(self, task_data: dict):
        """Create a new task."""
        task = self.repo.create(task_data)
        self.repo.commit()
        return task
```

### Option B: Service with Repository Manager (Recommended)

For services that need multiple repositories with coordinated transactions:

```python
from faststack.services.base_service import BaseService
from faststack.dependencies.repository_manager import repository_manager_dep
from faststack.repositories.repository_manager import RepositoryManager
from cfpbackend.src.session import SessionLocal

class TaskRepositoryManager(RepositoryManager[SessionLocal]):
    """Repository manager for task-related operations."""
    pass

class TaskService(BaseService):
    """Service for task-related operations using Repository Manager."""

    def __init__(self, rm: TaskRepositoryManager = repository_manager_dep(TaskRepositoryManager)):
        self.rm = rm

    def create_task_with_audit(self, task_data: dict):
        """Create task with audit log in coordinated transaction."""
        try:
            # Get repositories through manager
            task_repo = self.rm.get(TaskRepository)
            audit_repo = self.rm.get(AuditRepository)

            # Create task
            task = task_repo.create(task_data)
            self.rm.flush()  # Get task.id

            # Create audit log
            audit_repo.create({
                "action": "task_created",
                "task_id": task.id,
                "timestamp": datetime.utcnow()
            })

            # Commit both operations together
            self.rm.commit()
            return task

        except Exception:
            # Rollback all changes on error
            self.rm.rollback()
            raise
```

**When to use Repository Manager:**
- Service needs multiple repositories
- Operations require coordinated transactions
- You need to ensure data consistency across multiple entities

6. **Run your FastAPI application:**

```python
from faststack.run import run_fast_core_app
from settings import get_settings

app = run_fast_core_app(get_settings())
```

---

### Summary

- Install `faststack`.  
- Define **Settings** for all databases.  
- Register **Session** classes for each DB.  
- Define **repository** classes per model.  
- Define **service** classes and inject repositories.  
- Use `run_fast_core_app(get_settings())` instead of the normal FastAPI constructor.  

This setup provides a structured way to manage multiple databases, repositories, and services in a FastAPI project using FastStack.
