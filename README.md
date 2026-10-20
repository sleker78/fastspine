# FastStack

FastStack is an internal Python framework built on top of FastAPI that provides a service-repository
architecture, dependency injection, caching, and supporting infrastructure (database sessions, Celery
tasks, Alembic migrations, Redis, mailer) for building backend applications.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/) for dependency management

## Installation

```bash
make install
```

This runs `uv sync --group dev`, installing the project and its development dependencies.

## Core concepts

### Service-repository pattern

- **Repositories** (`AbstractRepository` / `BaseRepository`) encapsulate data access for a single
  entity or external data source, bound to a `Session` or `AsyncSession`.
- **Repository managers** (`RepositoryManager`) group related repositories that share the same
  database session, and expose transaction helpers (`sync_commit`, `sync_rollback`, ...).
- **Services** (`BaseService`) hold business logic and depend on repository managers and/or other
  services.

### Dependency injection

FastStack provides two parallel sets of dependency helpers for every layer:

- `*_dep` / `get_*` factories (e.g. `service_dep`, `get_repository`, `get_repository_manager`) —
  build FastAPI `Depends()`-compatible callables for use inside request handlers.
- `load_*` helpers (e.g. `load_service`, `load_repository`, `load_repository_manager`) — resolve the
  same dependency graph eagerly, for use outside of FastAPI's request lifecycle (CLI commands, Celery
  tasks, scripts).

### Caching

Decorators in `faststack.cache` (`cache_response`, `cache_method`, `cache_method_async`) cache
function results in Redis, with support for cache-key building, distributed locking to avoid
cache-stampede, and pluggable encoders.

### Other building blocks

- `faststack.database` — engine/session configuration for sync and async SQLAlchemy sessions.
- `faststack.celery` — base Celery task class integrated with the session/DI lifecycle.
- `faststack.alembic` — helpers for running Alembic migrations.
- `faststack.redis` — Redis client setup.
- `faststack.mailer` — email sending via `fastapi-mail`.
- `faststack.ctx` — context-local storage pool used throughout the framework for request/session
  scoping.

## Getting started

This walks through wiring up a new application on top of FastStack: bootstrapping the app,
registering databases, and defining repositories and services.

### 1. Bootstrap the app with `FastStackApp`

Instead of instantiating `fastapi.FastAPI` directly, use `FastStackApp`. It accepts every keyword
argument `FastAPI()` does, plus `settings` (your app's settings instance) and `use_asgi_middleware`
(set to `True` to use the ASGI-native middleware variants, required for streaming responses):

```python
from faststack import FastStackApp

from myapp.settings import AppSettings  # your pydantic_settings.BaseSettings subclass

app = FastStackApp(settings=AppSettings(), title="My App")
```

### 2. Define a `RepositoryManager` per database and register it

Each database/connection your app talks to gets its own `RepositoryManager` subclass, generic over
the session type it uses (`Session` for sync, `AsyncSession` for async):

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from faststack import RepositoryManager


class PrimaryRepositoryManager(RepositoryManager[Session]):
    """Repository manager for the main application database."""


class ReportingRepositoryManager(RepositoryManager[AsyncSession]):
    """Repository manager for an async reporting/warehouse database."""
```

Register each manager with the database it should connect to via `register_sessions` (or the
singular `register_session` / `register_async_session`), typically once at application startup:

```python
from faststack.database.engine import DBConfig, DBServices
from faststack.dependencies.database import register_sessions

register_sessions([
    (
        PrimaryRepositoryManager,
        DBConfig(dbname="app", user="app_user", host="localhost", port=5432, service=DBServices.POSTGRES),
    ),
    (
        ReportingRepositoryManager,
        DBConfig(
            dbname="reporting", user="reporting_user", host="reporting.internal", port=5432,
            service=DBServices.ASYNC_POSTGRES,
        ),
    ),
])
```

`DBConfig.async_mode` is derived automatically from `service` (the `ASYNC_*` variants), and must
match the session type the corresponding `RepositoryManager` is generic over.

### 3. Define repositories

Use `BaseRepository[Model]` for repositories backed by your own Alembic-tracked SQLAlchemy models
(subclassing FastStack's declarative `Base`), and `ExternalBaseRepository` for repositories that
talk to a database you don't own/migrate (raw queries, no ORM models):

```python
from faststack import BaseRepository, ExternalBaseRepository
from faststack.models.base import Base


class Order(Base):
    __tablename__ = "orders"
    # ... columns ...


class OrderRepository(BaseRepository[Order]):
    """Repository for `Order` rows in the primary database."""
    # inherits sync_get_by_id, sync_filter_by, sync_create, ... from BaseRepository


class ReportingRepository(ExternalBaseRepository):
    """Repository for ad-hoc queries against the reporting database."""

    async def get_monthly_totals(self) -> list[dict]:
        return await self.afetch_list("SELECT * FROM monthly_totals")
```

### 4. Define services that depend on one or more repository managers

A `BaseService` subclass declares the repository managers (and/or other services) it needs as
constructor parameters, typed by the manager class. FastStack's DI resolves and injects them:

```python
from faststack import BaseService


class OrderSyncService(BaseService):
    """Syncs order data between the primary database and the reporting database."""

    def __init__(
        self,
        primary: PrimaryRepositoryManager,
        reporting: ReportingRepositoryManager,
    ):
        self.primary = primary
        self.reporting = reporting

    def sync(self):
        orders = self.primary.get(OrderRepository).sync_filter_by()
        # ... push `orders` into the reporting database ...
```

### 5. Use the service

Inside a FastAPI route, inject it with `service_dep`:

```python
from fastapi import Depends

from faststack import service_dep

@app.post("/orders/sync")
def sync_orders(service: OrderSyncService = Depends(service_dep(OrderSyncService))):
    service.sync()
```

Outside of FastAPI's request lifecycle (CLI commands, Celery tasks), use `load_service` instead,
which resolves the same dependency graph eagerly:

```python
from faststack import load_service

def run_sync_job():
    service = load_service(OrderSyncService)
    service.sync()
```

## Development

Common tasks are available via `make`:

```bash
make install          # Install project + dev dependencies
make test              # Run the test suite with pytest
make ruff               # Run the ruff linter
make ruff-formatter     # Run the ruff formatter
make deptry             # Check for unused/missing dependencies
make mypy               # Run the mypy type checker
make check              # Run test, ruff-formatter, ruff, deptry and mypy
```

## License

Internal/proprietary — not published to a public package index.
