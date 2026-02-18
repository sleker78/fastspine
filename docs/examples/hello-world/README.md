# Hello World Example

The simplest possible FastStack application demonstrating core concepts.

## What This Example Shows

✅ **Basic FastStack setup** with minimal configuration
✅ **Database session registration** and automatic dependency injection
✅ **Repository pattern** with BaseRepository
✅ **Automatic table creation** on startup
✅ **Type-safe endpoints** with Pydantic models

## Prerequisites

- Python 3.10+
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

### 1. Database Configuration

```python
db_config = DBConfig(
    host="localhost",
    port=5432,
    dbname="faststack_hello",
    user="postgres",
    password="password",
    service="postgres"  # Uses psycopg2 driver
)
```

### 2. SQLAlchemy Model

```python
class Greeting(SQLBaseModel):
    __tablename__ = "greetings"

    id = Column(Integer, primary_key=True)
    message = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 3. Repository with Business Logic

```python
class GreetingRepository(BaseRepository[Greeting]):
    def __init__(self, db: Session, profiler: Profiler):
        super().__init__(db, profiler)

    def create_greeting(self, message: str) -> Greeting:
        greeting = Greeting(message=message)
        return self.create(greeting, commit=True)
```

### 4. Automatic Dependency Injection

```python
@app.post("/greetings", response_model=GreetingResponse)
async def create_greeting(
    message: str,
    greeting_repo: GreetingRepository = repository_dep(GreetingRepository)
    # ↑ FastStack automatically:
    # 1. Creates database session
    # 2. Injects profiler
    # 3. Instantiates repository
    # 4. Manages session lifecycle
):
    greeting = greeting_repo.create_greeting(message)
    return GreetingResponse.from_orm(greeting)
```

### 5. App Initialization

```python
# Register database session type
register_session(Session, db_config)

# Create FastStack app with all middleware
app = run_fast_core_app()
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
2. **Implement service layer** for business logic
3. **Add caching** with decorators
4. **Enable background tasks** with Celery
5. **Explore [Basic Blog Example](../basic-blog/)** for more complex patterns

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