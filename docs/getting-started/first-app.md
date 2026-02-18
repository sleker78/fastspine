# Your First FastStack Application

This guide will walk you through creating a complete FastStack application with users, posts, and comments - showcasing the framework's key features.

## Project Setup

Create a new project directory:

```bash
mkdir faststack-blog
cd faststack-blog

# Using uv (recommended)
uv init .
uv add faststack[all]

# Or using traditional virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install faststack[all]
```

## Project Structure

```
faststack-blog/
├── app/
│   ├── __init__.py
│   ├── main.py           # Application entry point
│   ├── models/           # SQLAlchemy models
│   ├── repositories/     # Data access layer (per database)
│   ├── services/         # Business logic (multi-database)
│   └── routers/         # API endpoints
├── config.py            # Configuration
├── pyproject.toml       # uv project file
└── uv.lock             # Dependency lock file
```

## Configuration

Create `config.py`:

```python
from functools import lru_cache
from pydantic_settings import BaseSettings
from faststack.database.engine import DBConfig

class Settings(BaseSettings):
    # Main Application Database
    APP_DB_HOST: str = "localhost"
    APP_DB_PORT: int = 5432
    APP_DB_NAME: str = "faststack_blog"
    APP_DB_USER: str = "postgres"
    APP_DB_PASSWORD: str = "password"

    # Analytics Database (optional)
    ANALYTICS_DB_HOST: str = "localhost"
    ANALYTICS_DB_PORT: int = 5432
    ANALYTICS_DB_NAME: str = "faststack_analytics"
    ANALYTICS_DB_USER: str = "postgres"
    ANALYTICS_DB_PASSWORD: str = "password"

    # Cache
    CACHE_ENABLED: bool = True
    REDIS_URL: str = "redis://localhost:6379/0"

    # App
    PROJECT_NAME: str = "FastStack Blog"
    DEBUG_MODE: bool = True

    @property
    def app_db_config(self) -> DBConfig:
        """Main application database configuration."""
        return DBConfig(
            host=self.APP_DB_HOST,
            port=self.APP_DB_PORT,
            dbname=self.APP_DB_NAME,
            user=self.APP_DB_USER,
            password=self.APP_DB_PASSWORD,
            service="postgres"
        )

    @property
    def analytics_db_config(self) -> DBConfig:
        """Analytics database configuration."""
        return DBConfig(
            host=self.ANALYTICS_DB_HOST,
            port=self.ANALYTICS_DB_PORT,
            dbname=self.ANALYTICS_DB_NAME,
            user=self.ANALYTICS_DB_USER,
            password=self.ANALYTICS_DB_PASSWORD,
            service="postgres"
        )

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

## Database Architecture

In this example, we use a **Primary + Analytics** database setup:

- **SessionApp** (Primary) - Business logic, Alembic migrations
- **SessionAnalytics** (Secondary) - Event logging, no migrations

This demonstrates FastStack's **"One Primary, Multiple Secondary"** pattern where:
- Primary database handles core business operations
- Analytics database handles event logging and metrics
- Each has its own Repository Manager for type-safe access

## Models

Create `app/models/user.py`:

```python
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from faststack.models.base import BaseModel
from faststack.mixins import SoftDeleteMixin

# PRIMARY DATABASE MODELS (Alembic-managed)
# These models will have migrations and live in the main app database

class User(BaseModel, SoftDeleteMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    posts = relationship("Post", back_populates="author")
    comments = relationship("Comment", back_populates="author")

class Post(BaseModel, SoftDeleteMixin):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text)
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    author = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")

class Comment(BaseModel):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"))
    author_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    post = relationship("Post", back_populates="comments")
    author = relationship("User", back_populates="comments")

# ANALYTICS DATABASE MODELS (Non-Alembic)
# These models live in the analytics database and don't have migrations

class UserEvent(BaseModel):
    """User event tracking for analytics database"""
    __tablename__ = "user_events"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)  # No FK constraint - different database
    event_type = Column(String(100), nullable=False)
    event_data = Column(Text)  # JSON data
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(45))
    user_agent = Column(Text)
```

## Repositories

Create `app/repositories/user_repository.py`:

```python
from typing import List
from sqlalchemy.orm import Session

from faststack.repositories.base_repository import BaseRepository
from faststack.lib.profiler import Profiler
from ..models.user import User

class UserRepository(BaseRepository[User]):
    """User repository with automatic session injection."""
    # NO __init__ needed! BaseRepository handles session injection via Repository Manager

    def find_by_email(self, email: str) -> User | None:
        """Find user by email address."""
        return self.filter_one(email=email)

    def find_by_username(self, username: str) -> User | None:
        """Find user by username."""
        return self.filter_one(username=username)

    def get_active_users(self) -> List[User]:
        """Get all non-deleted users."""
        return self.filter_by()  # Soft delete filtering is automatic

class PostRepository(BaseRepository[Post]):
    """Post repository with automatic session injection."""
    # NO __init__ needed! BaseRepository handles session injection

    def get_posts_by_author(self, author_id: int) -> List[Post]:
        """Get all posts by a specific author."""
        return self.filter_by(self.model.author_id == author_id)

    def get_recent_posts(self, limit: int = 10) -> List[Post]:
        """Get recent posts with limit."""
        return (self.db.query(self.model)
                .order_by(self.model.created_at.desc())
                .limit(limit)
                .all())
```

## Services

Create `app/services/blog_service.py`:

```python
from typing import List
from sqlalchemy.orm import Session
from faststack.services.base_service import BaseService
from faststack.cache.cache_decorater import cache_method_async
from faststack.repositories.repository_manager import RepositoryManager
from faststack.dependencies.repository_manager import repository_manager_dep
from ..repositories.user_repository import UserRepository, PostRepository
from ..models.user import User, Post

# Import Repository Manager classes from main.py
from ..main import AppRepositoryManager, AnalyticsRepositoryManager

class BlogService(BaseService):
    """Business logic for blog operations with multi-database support."""

    def __init__(self,
        profiler: Profiler = Depends(get_profiler),
        app_rm: AppRepositoryManager = repository_manager_dep(AppRepositoryManager),
        analytics_rm: AnalyticsRepositoryManager = repository_manager_dep(AnalyticsRepositoryManager)
    ):
        super().__init__()
        self.profiler = profiler
        self.app_rm = app_rm          # Main application database
        self.analytics_rm = analytics_rm  # Analytics database

    @cache_method_async(expire=300)  # Cache for 5 minutes
    async def create_user(self, email: str, username: str, full_name: str | None = None) -> User:
        """Create a new user with business logic validation."""
        user_repo = self.app_rm.get(UserRepository)

        # Business logic: Check if user already exists
        if user_repo.find_by_email(email):
            raise ValueError(f"User with email {email} already exists")

        if user_repo.find_by_username(username):
            raise ValueError(f"Username {username} is already taken")

        user = User(email=email, username=username, full_name=full_name)
        return user_repo.create(user, commit=True)

    @cache_method_async(expire=300)
    async def get_user_by_id(self, user_id: int) -> User | None:
        """Get user by ID with caching."""
        user_repo = self.app_rm.get(UserRepository)

        # Log analytics (using separate database)
        # Note: In real apps, you might have AnalyticsEvent model
        # analytics_repo = self.analytics_rm.get(AnalyticsRepository)
        # analytics_repo.track_user_view(user_id)

        return user_repo.get_by_id(user_id)

    @cache_method_async(expire=60)
    async def get_user_posts(self, user_id: int, limit: int = 10) -> List[Post]:
        """Get user's posts with caching."""
        post_repo = self.app_rm.get(PostRepository)
        return post_repo.get_posts_by_author(user_id)[:limit]
```

## API Endpoints

Create `app/routers/users.py`:

```python
from typing import List
from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from faststack.dependencies.services import service_dep
from ..services.blog_service import BlogService
from ..models.user import User, Post

router = APIRouter(prefix="/users", tags=["users"])

# Response models
class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str | None = None

    class Config:
        from_attributes = True

class PostResponse(BaseModel):
    id: int
    title: str
    content: str | None = None
    author_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class CreateUserRequest(BaseModel):
    email: str
    username: str
    full_name: str | None = None

@router.post("/", response_model=UserResponse)
async def create_user(
    request: CreateUserRequest,
    blog_service: BlogService = service_dep(BlogService)
) -> UserResponse:
    """Create a new user via service layer."""
    try:
        user = await blog_service.create_user(
            email=request.email,
            username=request.username,
            full_name=request.full_name
        )
        return UserResponse.from_orm(user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    blog_service: BlogService = service_dep(BlogService)
) -> UserResponse:
    """Get user by ID via service layer."""
    user = await blog_service.get_user_by_id(user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return UserResponse.from_orm(user)

@router.get("/{user_id}/posts", response_model=List[PostResponse])
async def get_user_posts(
    user_id: int,
    limit: int = 10,
    blog_service: BlogService = service_dep(BlogService)
) -> List[PostResponse]:
    """Get user's posts via service layer."""
    posts = await blog_service.get_user_posts(user_id, limit)
    return [PostResponse.from_orm(post) for post in posts]
```

## Main Application

Create `app/main.py`:

```python
from contextlib import asynccontextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from faststack.repositories.repository_manager import RepositoryManager

from faststack import run_fast_core_app
from faststack.dependencies.database import register_sessions
from faststack.models.base import BaseModel

from config import settings
from .routers import users

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

# Database setup
def create_tables():
    """Create database tables for all databases."""
    # Create tables for main app database
    app_engine = settings.app_db_config.create_engine()
    BaseModel.metadata.create_all(app_engine)

    # Create tables for analytics database (optional)
    analytics_engine = settings.analytics_db_config.create_engine()
    BaseModel.metadata.create_all(analytics_engine)

@asynccontextmanager
async def lifespan(app):
    """Application lifespan events."""
    # Startup
    create_tables()
    print(f"🚀 {settings.PROJECT_NAME} started!")

    yield

    # Shutdown
    print("👋 Application shutting down...")

def create_app():
    """Create and configure FastStack application."""

    # Register multiple database sessions
    register_sessions([
        (SessionApp, settings.app_db_config),
        (SessionAnalytics, settings.analytics_db_config),
    ])

    # Create FastStack app
    app = run_fast_core_app(
        settings=settings,
        use_asgi_middleware=True  # Use ASGI for better performance
    )

    # Add lifespan
    app.router.lifespan_context = lifespan

    # Include routers
    app.include_router(users.router)

    return app

# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
```

## Running the Application

```bash
# Using uv (recommended)
uv add uvicorn
uv run python -m app.main

# Or using traditional approach
pip install uvicorn
python -m app.main

# Or use uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Testing Your API

```bash
# Create a user
curl -X POST "http://localhost:8000/users/" \
     -H "Content-Type: application/json" \
     -d '{
       "email": "john@example.com",
       "username": "john_doe",
       "full_name": "John Doe"
     }'

# Get the user
curl "http://localhost:8000/users/1"
```

## What You've Accomplished

✅ **Multi-layer architecture** - Models, Repositories, Services, Endpoints
✅ **Automatic dependency injection** - No manual wiring required
✅ **Database integration** - PostgreSQL with session management
✅ **Soft delete support** - Users can be soft-deleted
✅ **Caching integration** - Service methods cached automatically
✅ **Type safety** - Full type hints throughout
✅ **Request-scoped resources** - Automatic cleanup

## Next Steps

- **[Configuration Guide](configuration.md)** - Advanced settings
- **[Architecture Deep Dive](../guides/architecture.md)** - Understand the magic
- **[Caching Strategies](../guides/caching.md)** - Optimize performance
- **[Testing Patterns](../guides/testing.md)** - Test your application