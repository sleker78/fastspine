# 🚀 FastStack

**The FastAPI framework that gets you from zero to production in minutes, not hours.**

FastStack is a batteries-included FastAPI framework designed for developers who want to build production-ready APIs without the boilerplate. Get instant access to database operations, dependency injection, async support, and more—all pre-configured and ready to use.

## ✨ Why FastStack?

- **⚡ Instant Database Access** - Pre-configured SQLAlchemy with async support, connection pooling, and repository patterns
- **🔧 Zero Configuration** - Jump straight into building features, not setting up infrastructure
- **📦 Built-in Patterns** - Repository pattern, service layer, dependency injection, and error handling out of the box
- **🔄 Async-First** - Full async/await support for high-performance applications
- **⏱️ Model Mixins** - Timestamps, soft deletes, and other common patterns included
- **📊 Performance Profiling** - Built-in profiling and monitoring tools
- **🎯 Type-Safe** - Full type hints and Pydantic integration throughout

## 🚦 Quick Start

```bash
# Get started in 30 seconds
git clone <your-repo>
cd faststack
uv sync --extra dev
```

**That's it!** You now have:
- ✅ FastAPI app with async database support
- ✅ SQLAlchemy models with automatic timestamps
- ✅ Repository pattern for clean data access
- ✅ Dependency injection system
- ✅ Error handling and validation
- ✅ Celery for background tasks
- ✅ Redis integration

## 🔥 What You Get Out of the Box

### Database Made Simple
```python
from faststack import BaseRepository, repository_dep

class UserRepository(BaseRepository[User]):
    async def find_by_email(self, email: str) -> User | None:
        return await self.find_one_by(User.email == email)

# Automatic dependency injection
@app.get("/users/{user_id}")
async def get_user(user_id: int, repo: UserRepository = repository_dep()):
    return await repo.find_by_id(user_id)
```

### Models with Smart Mixins
```python
from faststack.models.base import Base
from faststack.mixins import CreatedAtMixin, SoftDeleteMixin

class User(Base, CreatedAtMixin, SoftDeleteMixin):
    name = Column(String(100))
    email = Column(String(255), unique=True)
    # created_at, updated_at, deleted_at automatically added!
```

### Service Layer Pattern
```python
from faststack import BaseService, service_dep

class UserService(BaseService):
    async def create_user(self, data: UserCreateSchema) -> User:
        # Business logic here - validation, transformation, etc.
        return await self.repo.create(data.dict())

@app.post("/users")
async def create_user(
    data: UserCreateSchema,
    service: UserService = service_dep()
):
    return await service.create_user(data)
```

## 🛠️ Advanced Features

- **Connection Pool Management** - Automatic database connection handling
- **Background Tasks** - Celery integration with Redis backend
- **Performance Profiling** - Built-in request profiling and monitoring
- **Data Processing** - Pandas and Polars integration for data manipulation
- **Email Support** - FastAPI-Mail integration
- **Excel Export** - Built-in support for spreadsheet generation

## 🏗️ Using FastStack in Your Project

**Install FastStack:**
```bash
# Add to your project
uv add faststack

# Or with pip
pip install faststack
```

**Create your first FastStack app:**
```python
from faststack import run_fast_core_app
from config import settings

# FastStack creates and configures the FastAPI app for you
app = run_fast_core_app(settings)
```

## 🔧 Contributing to FastStack

**For FastStack framework development:**

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency management

### Development Commands
```bash
make install  # Install FastStack development dependencies
make test     # Run FastStack framework tests
make check    # Run all quality checks on framework code
```

---

## 🤝 Contributing

FastStack is designed to make FastAPI development faster and more enjoyable. Contributions welcome!

## 📄 License

This project is licensed under the MIT License.
