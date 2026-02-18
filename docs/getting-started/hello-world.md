# Hello World - Simplest FastStack App

The absolute simplest FastStack application demonstrating core concepts with minimal setup.

## What You'll Build

A basic API with:
- ✅ Single database connection
- ✅ One model (Greeting)
- ✅ One repository
- ✅ One service
- ✅ One endpoint
- ✅ Automatic dependency injection

## Prerequisites

- Python 3.12+
- PostgreSQL running locally

## Quick Start

### 1. Project Setup

```bash
mkdir faststack-hello
cd faststack-hello

# Using uv (recommended)
uv init .
uv add faststack[all]
uv add uvicorn

# Or traditional setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install faststack[all] uvicorn
```

### 2. Database Setup

```bash
# Using Docker
docker run --name hello-db \
  -e POSTGRES_DB=hello_world \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -d postgres:15

# Or create database manually
createdb hello_world
```

### 3. Single File Application

Create `main.py`:

```python
from datetime import datetime
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from faststack import run_fast_core_app
from faststack.database.engine import DBConfig
from faststack.dependencies.database import register_sessions
from faststack.dependencies.repository_manager import repository_manager_dep
from faststack.dependencies.services import service_dep
from faststack.models.base import BaseModel as SQLBaseModel
from faststack.repositories.base_repository import BaseRepository
from faststack.repositories.repository_manager import RepositoryManager
from faststack.services.base_service import BaseService

# Database Configuration
DB_CONFIG = DBConfig(
    host="localhost",
    port=5432,
    dbname="hello_world",
    user="postgres",
    password="password",
    service="postgres"
)

# Session Definition
class SessionLocal(Session):
    """Main database session"""
    pass

# Repository Manager
class LocalRepositoryManager(RepositoryManager[SessionLocal]):
    """Repository manager for local database"""
    pass

# SQLAlchemy Model
class Greeting(SQLBaseModel):
    __tablename__ = "greetings"

    id = Column(Integer, primary_key=True)
    message = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# Pydantic Response Model
class GreetingResponse(BaseModel):
    id: int
    message: str
    created_at: datetime

    class Config:
        from_attributes = True

# Repository
class GreetingRepository(BaseRepository[Greeting]):
    """Greeting repository - NO __init__ needed!"""

    def get_latest(self, limit: int = 10) -> list[Greeting]:
        """Get latest greetings."""
        return (self.db.query(self.model)
                .order_by(self.model.created_at.desc())
                .limit(limit)
                .all())

# Service
class GreetingService(BaseService):
    """Greeting service with automatic DI"""

    def __init__(self,
        rm: LocalRepositoryManager = repository_manager_dep(LocalRepositoryManager)
    ):
        super().__init__()
        self.rm = rm

    def create_greeting(self, message: str) -> Greeting:
        """Create a new greeting"""
        repo = self.rm.get(GreetingRepository)
        greeting = Greeting(message=message)
        return repo.create(greeting, commit=True)

    def get_greetings(self, limit: int = 10) -> list[Greeting]:
        """Get latest greetings"""
        repo = self.rm.get(GreetingRepository)
        return repo.get_latest(limit)

# Register database session
register_sessions([(SessionLocal, DB_CONFIG)])

# Create FastStack app
app = run_fast_core_app()

# Create tables on startup
@app.on_event("startup")
async def create_tables():
    """Create database tables"""
    engine = DB_CONFIG.create_engine()
    SQLBaseModel.metadata.create_all(engine)
    print("🚀 Hello World app started!")

# API Endpoints
@app.get("/")
async def root():
    """Simple hello endpoint"""
    return {"message": "Hello FastStack World!"}

@app.post("/greetings", response_model=GreetingResponse)
async def create_greeting(
    message: str,
    greeting_service: GreetingService = service_dep(GreetingService)
) -> GreetingResponse:
    """Create a greeting with automatic DI"""
    greeting = greeting_service.create_greeting(message)
    return GreetingResponse.from_orm(greeting)

@app.get("/greetings", response_model=list[GreetingResponse])
async def get_greetings(
    limit: int = 10,
    greeting_service: GreetingService = service_dep(GreetingService)
) -> list[GreetingResponse]:
    """Get latest greetings"""
    greetings = greeting_service.get_greetings(limit)
    return [GreetingResponse.from_orm(g) for g in greetings]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

### 4. Run the Application

```bash
# Using uv
uv run python main.py

# Or directly
python main.py

# Or with uvicorn
uvicorn main:app --reload
```

Visit: `http://localhost:8000`

## Test Your API

### Create a greeting:
```bash
curl -X POST "http://localhost:8000/greetings?message=Hello%20FastStack!"
```

Response:
```json
{
  "id": 1,
  "message": "Hello FastStack!",
  "created_at": "2024-01-01T12:00:00.000Z"
}
```

### Get greetings:
```bash
curl "http://localhost:8000/greetings"
```

Response:
```json
[
  {
    "id": 1,
    "message": "Hello FastStack!",
    "created_at": "2024-01-01T12:00:00.000Z"
  }
]
```

## What FastStack Provides

Even in this simple example, you get:

### ✅ **Zero-Configuration Dependency Injection**
```python
greeting_service: GreetingService = service_dep(GreetingService)
# FastStack automatically:
# 1. Creates database session
# 2. Creates Repository Manager
# 3. Injects into Service
# 4. Manages session lifecycle
```

### ✅ **Repository Pattern with No Boilerplate**
```python
class GreetingRepository(BaseRepository[Greeting]):
    # NO __init__ needed - session injected automatically!

    def get_latest(self, limit: int = 10):
        return self.db.query(self.model)...  # self.db available automatically
```

### ✅ **Service Layer with Clean Architecture**
```python
class GreetingService(BaseService):
    def __init__(self, rm: LocalRepositoryManager = repository_manager_dep(...)):
        # Repository Manager injected automatically

    def create_greeting(self, message: str):
        repo = self.rm.get(GreetingRepository)  # Type-safe repository access
```

### ✅ **Automatic Database Management**
- Session creation and cleanup
- Connection pooling
- Transaction management
- Table creation

## Interactive Documentation

Visit `http://localhost:8000/docs` for Swagger UI with automatic API documentation.

## What's Happening Behind the Scenes

1. **`register_sessions()`** creates `get_sessionlocal_db()` function
2. **`repository_manager_dep()`** resolves `LocalRepositoryManager` with database session
3. **`service_dep()`** creates `GreetingService` with all dependencies
4. **Repository Manager** lazily loads repositories with `.get()`
5. **FastStack middleware** manages request lifecycle and cleanup

## Next Steps

This hello-world shows FastStack fundamentals. To explore more:

- **[First App Tutorial](first-app.md)** - Multi-database blog application
- **[Architecture Guide](../guides/architecture.md)** - How it all works
- **[Configuration](configuration.md)** - Advanced settings

## File Structure

```
faststack-hello/
├── main.py          # Complete application
├── pyproject.toml   # uv dependencies
└── uv.lock         # Dependency lock file
```

**That's it! A complete FastStack application in ~100 lines with enterprise-grade patterns.** 🚀