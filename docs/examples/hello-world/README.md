# Hello World Example

The simplest possible FastStack application demonstrating core concepts.

## What This Example Shows

✅ **Basic FastStack setup** with settings-based configuration
✅ **Service-Repository pattern** with automatic dependency injection
✅ **Repository pattern** with BaseRepository (no manual __init__)
✅ **Business logic separation** in service layer
✅ **Type-safe endpoints** with modern Pydantic models

## Prerequisites

- Python 3.12+
- PostgreSQL database
- Basic understanding of FastAPI

## Quick Start

### 1. Set Up Database

```bash
# Using Docker (recommended)
docker run --name faststack-hello-db \
  -e POSTGRES_DB=faststack_hello \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -d postgres:15

# Or use your existing PostgreSQL instance
createdb faststack_hello
```

### 2. Install Dependencies

```bash
pip install faststack uvicorn
```

### 3. Run the Application

```bash
python main.py
```

The application will start on `http://localhost:8000`

## API Endpoints

### GET /
Simple hello world endpoint.

```bash
curl http://localhost:8000/
# Response: {"message": "Hello FastStack World!"}
```

### GET /health
Health check endpoint.

```bash
curl http://localhost:8000/health
# Response: {"status": "healthy", "timestamp": "2024-01-01T12:00:00.000Z"}
```

### POST /greetings
Create a new greeting.

```bash
curl -X POST "http://localhost:8000/greetings?message=Hello%20from%20API" \
  -H "Content-Type: application/json"
```

Response:
```json
{
  "id": 1,
  "message": "Hello from API",
  "created_at": "2024-01-01T12:00:00.000Z"
}
```

### GET /greetings
Get the latest greetings.

```bash
curl http://localhost:8000/greetings?limit=5
```

Response:
```json
[
  {
    "id": 1,
    "message": "Hello from API",
    "created_at": "2024-01-01T12:00:00.000Z"
  }
]
```

## Code Walkthrough

### 1. Settings-Based Configuration

```python
class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "faststack_hello"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"

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
```

### 2. SQLAlchemy Model

```python
class Greeting(SQLBaseModel):
    __tablename__ = "greetings"

    id = Column(Integer, primary_key=True)
    message = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=now)  # Using FastStack utility
```

### 3. Repository with Automatic Injection

```python
class GreetingRepository(BaseRepository[Greeting]):
    # No __init__ needed! BaseRepository handles session injection automatically

    def create_greeting(self, message: str) -> Greeting:
        greeting = Greeting(message=message)
        return self.create(greeting, commit=True)
```

### 4. Service Layer with Business Logic

```python
# Repository Manager for dependency injection
class LocalRepositoryManager(RepositoryManager[Session]):
    pass

class GreetingService(BaseService):
    def __init__(self, rm: LocalRepositoryManager = repository_manager_dep(LocalRepositoryManager)):
        super().__init__()
        self.rm = rm

    async def create_greeting(self, message: str) -> Greeting:
        # Business logic - validation, transformation, etc.
        if not message.strip():
            raise ValueError("Message cannot be empty")

        repo = self.rm.get(GreetingRepository)
        return repo.create_greeting(message.strip())

@app.post("/greetings", response_model=GreetingResponse)
async def create_greeting(
    message: str,
    service: GreetingService = service_dep(GreetingService)
    # ↑ FastStack automatically:
    # 1. Creates database session
    # 2. Injects repository manager
    # 3. Instantiates service
    # 4. Manages session lifecycle
):
    greeting = await service.create_greeting(message)
    return GreetingResponse.model_validate(greeting)
```

### 5. App Initialization

```python
# Register database session type
register_session(Session, settings.db_config)

# Create FastStack app with settings
app = run_fast_core_app(settings)
```

## Key FastStack Concepts Demonstrated

### Automatic Dependency Injection
- No manual wiring of dependencies
- Type-safe parameter resolution
- Automatic session lifecycle management

### Repository Pattern
- Generic `BaseRepository[T]` with automatic model extraction
- Built-in CRUD operations
- Transaction management

### Configuration-Driven Setup
- `DBConfig` for database settings
- `register_session()` for dependency registration
- `run_fast_core_app()` for app creation

## What Happens Behind the Scenes

1. **Session Registration**: `register_session()` creates `get_session_db()` function
2. **Dependency Resolution**: `repository_dep()` analyzes constructor types
3. **Request Processing**: Middleware sets up session pool and profiler
4. **Repository Creation**: Dependencies automatically injected
5. **Session Cleanup**: Database connections closed after request

## Interactive Testing

Visit `http://localhost:8000/docs` for interactive API documentation.

## Next Steps

From this basic example, you can:

1. **Add more models** and repositories
2. **Expand service layer** with advanced business logic
3. **Add caching** with decorators
4. **Enable background tasks** with Celery
5. **Explore [Basic Blog Example](../basic-blog/)** for multi-database patterns

## Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5432

# Test connection manually
psql -h localhost -p 5432 -U postgres -d faststack_hello
```

### Import Errors
```bash
# Ensure FastStack is installed
pip install faststack

# Or install in development mode
pip install -e /path/to/faststack
```

### Port Already in Use
```bash
# Use different port
uvicorn main:app --port 8001

# Or find and kill process using port 8000
lsof -ti:8000 | xargs kill
```