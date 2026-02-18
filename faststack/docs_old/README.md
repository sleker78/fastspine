# FastStack

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A powerful Python library designed to accelerate FastAPI application development with enterprise-grade patterns and utilities.

## 🚀 Features

- **🏗️ Dependency Injection (DI):** Streamlined dependency management for FastAPI applications
- **🗄️ Session Handling:** Simplified database session management with multi-database support
- **🏛️ Service/Repository Pattern:** Clean architecture with clear separation of concerns
- **⚡ Caching Support:** Built-in Redis integration for improved performance
- **📧 Mailer Service:** Email functionality with templating and attachment support
- **🔄 Celery Integration:** Async task queue management
- **🛠️ Utility Classes:** Helper classes to reduce boilerplate code

## 📦 Installation

```bash
uv add faststack
```

Or with pip:
```bash
pip install faststack
```

## ⚡ Quick Start

### 1. Define Settings

```python
from pydantic import BaseSettings
from pydantic_settings import SettingsConfigDict

class Settings(BaseSettings):
    """Application settings and secrets management."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # App specific settings
    DEBUG_MODE: bool = True
    PROJECT_NAME: str = "my-project"
    APP_SECRET: str = "change-me-in-production"
    PUBLIC_URL: str = "http://localhost:8000/"

@lru_cache()
def get_settings() -> Settings:
    """Get the application settings with caching."""
    return Settings()
```

### 2. Create FastAPI App

```python
from faststack.run import run_fast_core_app
from settings import get_settings

# Instead of: app = FastAPI()
app = run_fast_core_app(get_settings())
```

### 3. Setup Database Sessions

```python
from faststack import RepositoryManager
from faststack.dependencies.database import register_sessions
from sqlalchemy.orm import Session

class SessionLocal(Session):
    """Session for main database."""
    pass

class RepositoryManagerLocal(RepositoryManager[SessionLocal]):
    """Repository manager for main DB operations."""
    pass

# Register sessions
register_sessions([
    (SessionLocal, get_settings().DB_CONFIG),
])
```

### 4. Create Repositories

```python
from faststack import BaseRepository
from models import User

class UserRepository(BaseRepository[User]):
    """User repository with CRUD operations."""
    pass
```

### 5. Build Services

```python
from faststack.services.base_service import BaseService
from faststack.dependencies.repositories import repository_dep

class UserService(BaseService):
    """User business logic service."""

    def __init__(self, user_repo: UserRepository = repository_dep(UserRepository)):
        self.user_repo = user_repo

    def create_user(self, user_data: dict):
        """Create a new user."""
        user = self.user_repo.create(user_data)
        self.user_repo.commit()
        return user
```

## 🏗️ Architecture Patterns

### Repository Pattern
FastStack implements the repository pattern for clean data access:

```python
# Available repository methods:
user = user_repo.get_by_id(1)
users = user_repo.filter_by(active=True)
user_repo.create(user_data)
user_repo.delete(user)
user_repo.commit()
```

### Service Layer
Keep business logic in services:

```python
class UserService(BaseService):
    def register_user(self, email: str, password: str):
        # Business logic here
        if self.user_repo.filter_one(email=email):
            raise ValueError("User already exists")
        return self.user_repo.create({"email": email, "password": hash(password)})
```

### Repository Manager
For coordinated transactions across multiple repositories:

```python
class UserService(BaseService):
    def __init__(self, rm: UserRepositoryManager = repository_manager_dep(UserRepositoryManager)):
        self.rm = rm

    def create_user_with_profile(self, user_data: dict, profile_data: dict):
        try:
            user_repo = self.rm.get(UserRepository)
            profile_repo = self.rm.get(ProfileRepository)

            user = user_repo.create(user_data)
            self.rm.flush()  # Get user.id

            profile_data["user_id"] = user.id
            profile_repo.create(profile_data)

            self.rm.commit()  # Commit both operations
            return user
        except Exception:
            self.rm.rollback()
            raise
```

## 🗄️ Database Support

FastStack supports multiple databases with both sync and async modes:

- **PostgreSQL** (sync: `postgres`, async: `async_postgres`)
- **MySQL** (sync: `mysql`, async: `async_mysql`)

### Async Support

```python
from sqlalchemy.ext.asyncio import AsyncSession

class AsyncSessionLocal(AsyncSession):
    """Async session for main database."""
    pass
```

## 📧 Email Service

```python
from faststack.services.mailer import MailerService

mailer = MailerService()
await mailer.send_email(
    to="user@example.com",
    subject="Welcome!",
    template="welcome.html",
    context={"name": "John"}
)
```

## ⚡ Caching

Built-in Redis caching support:

```python
from faststack.cache import cache_manager

@cache_manager.cached(ttl=300)
def expensive_operation(param: str):
    # This result will be cached for 5 minutes
    return complex_calculation(param)
```

## 🔄 Celery Integration

Async task processing:

```python
from faststack.celery import celery_app

@celery_app.task
def send_notification(user_id: int):
    # Background task logic
    pass
```

## 📚 Documentation

- [Quick Start Guide](QuickView.md) - Detailed setup and usage examples
- [API Reference](api/) - Complete API documentation
- [Examples](examples/) - Sample applications and patterns

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- Create an issue for bug reports or feature requests
- Check the documentation for usage examples
- Community discussions welcome!

---

**FastStack** - Accelerating FastAPI development with proven enterprise patterns.