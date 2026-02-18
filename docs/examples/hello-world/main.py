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
from faststack.lib.profiler import Profiler
from faststack.models.base import BaseModel as SQLBaseModel
from faststack.repositories.base_repository import BaseRepository

# Configuration
db_config = DBConfig(
    host="localhost", port=5432, dbname="faststack_hello", user="postgres", password="password", service="postgres"
)


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
    def __init__(self, db: Session, profiler: Profiler):
        super().__init__(db, profiler)

    def create_greeting(self, message: str) -> Greeting:
        """Create a new greeting."""
        greeting = Greeting(message=message)
        return self.create(greeting, commit=True)

    def get_latest_greetings(self, limit: int = 10) -> list[Greeting]:
        """Get the latest greetings."""
        return self.db.query(self.model).order_by(self.model.created_at.desc()).limit(limit).all()


# Register database session
register_session(Session, db_config)

# Create FastStack app
app = run_fast_core_app()


# Create tables
@app.on_event("startup")
async def create_tables():
    """Create database tables on startup."""
    engine = db_config.create_engine()
    SQLBaseModel.metadata.create_all(engine)


# Routes
@app.get("/")
async def root():
    """Simple hello world endpoint."""
    return {"message": "Hello FastStack World!"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow()}


@app.post("/greetings", response_model=GreetingResponse)
async def create_greeting(
    message: str, greeting_repo: GreetingRepository = repository_dep(GreetingRepository)
) -> GreetingResponse:
    """Create a new greeting with automatic dependency injection."""
    greeting = greeting_repo.create_greeting(message)
    return GreetingResponse.from_orm(greeting)


@app.get("/greetings", response_model=list[GreetingResponse])
async def get_greetings(
    limit: int = 10, greeting_repo: GreetingRepository = repository_dep(GreetingRepository)
) -> list[GreetingResponse]:
    """Get the latest greetings."""
    greetings = greeting_repo.get_latest_greetings(limit)
    return [GreetingResponse.from_orm(g) for g in greetings]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
