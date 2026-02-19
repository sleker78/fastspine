"""FastStack Hello World Example

The simplest possible FastStack application demonstrating:
- Basic app setup
- Database session registration
- Simple endpoint with dependency injection
"""

from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import Session

from faststack import run_fast_core_app
from faststack.database.engine import DBConfig
from faststack.dependencies.database import register_session
from faststack.dependencies.repositories import repository_dep
from faststack.dependencies.services import service_dep
from faststack.lib.profiler import Profiler
from faststack.models.base import BaseModel as SQLBaseModel
from faststack.repositories.base_repository import BaseRepository
from faststack.util.dates import now
from pydantic_settings import BaseSettings

# Configuration
class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "faststack_hello"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    PROJECT_NAME: str = "FastStack Hello World"

    @property
    def db_config(self) -> DBConfig:
        return DBConfig(
            host=self.DB_HOST,
            port=self.DB_PORT,
            dbname=self.DB_NAME,
            user=self.DB_USER,
            password=self.DB_PASSWORD,
            service="postgres"
        )

settings = Settings()


# SQLAlchemy Model
class Greeting(SQLBaseModel):
    __tablename__ = "greetings"

    id = Column(Integer, primary_key=True)
    message = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=now)


# Pydantic Response Model
class GreetingResponse(BaseModel):
    id: int
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


# Repository
class GreetingRepository(BaseRepository[Greeting]):
    """Repository for greeting data access - automatic session injection."""

    def create_greeting(self, message: str) -> Greeting:
        """Create a new greeting."""
        greeting = Greeting(message=message)
        return self.create(greeting, commit=True)

    def get_latest_greetings(self, limit: int = 10) -> list[Greeting]:
        """Get the latest greetings."""
        return self.db.query(self.model).order_by(self.model.created_at.desc()).limit(limit).all()


# Service
from faststack.services.base_service import BaseService
from faststack.dependencies.repository_manager import repository_manager_dep
from faststack.repositories.repository_manager import RepositoryManager

class LocalRepositoryManager(RepositoryManager[Session]):
    """Repository manager for local session."""
    pass

class GreetingService(BaseService):
    """Service for greeting business logic."""

    def __init__(self, rm: LocalRepositoryManager = repository_manager_dep(LocalRepositoryManager)):
        super().__init__()
        self.rm = rm

    async def create_greeting(self, message: str) -> Greeting:
        """Create greeting with business logic."""
        # Business logic here (validation, transformation, etc.)
        if not message.strip():
            raise ValueError("Message cannot be empty")

        repo = self.rm.get(GreetingRepository)
        return repo.create_greeting(message.strip())

    async def get_greetings(self, limit: int = 10) -> list[Greeting]:
        """Get greetings with business logic."""
        if limit > 100:
            limit = 100  # Business rule: max 100 results

        repo = self.rm.get(GreetingRepository)
        return repo.get_latest_greetings(limit)


# Register database session
register_session(Session, settings.db_config)

# Create FastStack app
app = run_fast_core_app(settings)

# Routes
@app.get("/")
async def root():
    """Simple hello world endpoint."""
    return {"message": "Hello FastStack World!"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": now()}


@app.post("/greetings", response_model=GreetingResponse)
async def create_greeting(
    message: str,
    greeting_service: GreetingService = service_dep(GreetingService)
) -> GreetingResponse:
    """Create a new greeting with automatic dependency injection."""
    greeting = await greeting_service.create_greeting(message)
    return GreetingResponse.model_validate(greeting)


@app.get("/greetings", response_model=list[GreetingResponse])
async def get_greetings(
    limit: int = 10,
    greeting_service: GreetingService = service_dep(GreetingService)
) -> list[GreetingResponse]:
    """Get the latest greetings."""
    greetings = await greeting_service.get_greetings(limit)
    return [GreetingResponse.model_validate(g) for g in greetings]


if __name__ == "__main__":
    # NOTE: This is for development only!
    # For production, use a proper ASGI server like:
    # uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
    # or gunicorn with uvicorn workers
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
