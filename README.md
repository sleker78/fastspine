# FastStack

FastStack is an Python framework built on top of FastAPI that provides a service-repository
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

### 2. Configure settings with a `DBConfig` per database

Group each database's connection fields in your settings class, and expose a `DBConfig` (or
`DBReadonlyConfig`) for each one as a property. `service` determines the driver/dialect and whether
the connection is async (`DBConfig.async_mode` is derived automatically from it):

```python
from pydantic_settings import BaseSettings

from faststack.database.engine import DBConfig, DBServices


class AppSettings(BaseSettings):
    PRIMARY_DB_NAME: str = "app"
    PRIMARY_DB_USER: str = "app_user"
    PRIMARY_DB_PASSWORD: str = ""
    PRIMARY_DB_HOST: str = "localhost"
    PRIMARY_DB_PORT: int = 5432

    REPORTING_DB_NAME: str = "reporting"
    REPORTING_DB_USER: str = "reporting_user"
    REPORTING_DB_PASSWORD: str = ""
    REPORTING_DB_HOST: str = "reporting.internal"
    REPORTING_DB_PORT: int = 5432

    @property
    def primary_db_config(self) -> DBConfig:
        return DBConfig(
            dbname=self.PRIMARY_DB_NAME,
            user=self.PRIMARY_DB_USER,
            password=self.PRIMARY_DB_PASSWORD,
            host=self.PRIMARY_DB_HOST,
            port=self.PRIMARY_DB_PORT,
            service=DBServices.POSTGRES,
        )

    @property
    def reporting_db_config(self) -> DBConfig:
        return DBConfig(
            dbname=self.REPORTING_DB_NAME,
            user=self.REPORTING_DB_USER,
            password=self.REPORTING_DB_PASSWORD,
            host=self.REPORTING_DB_HOST,
            port=self.REPORTING_DB_PORT,
            service=DBServices.ASYNC_POSTGRES,
        )


settings = AppSettings()
```

### 3. Define a `RepositoryManager` per database and register it, via a dedicated bootstrap module

Each database/connection your app talks to gets its own `RepositoryManager` subclass, generic over
the session type it uses (`Session` for sync, `AsyncSession` for async). Define them together with
the `register_sessions(...)` call that wires each one to its `DBConfig`, in one small, dedicated
module (e.g. `myapp/bootstrap.py`):

```python
# myapp/bootstrap.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from faststack import RepositoryManager
from faststack.dependencies.database import register_sessions

from myapp.settings import settings


class PrimaryRepositoryManager(RepositoryManager[Session]):
    """Repository manager for the main application database."""


class ReportingRepositoryManager(RepositoryManager[AsyncSession]):
    """Repository manager for an async reporting/warehouse database."""


register_sessions([
    (PrimaryRepositoryManager, settings.primary_db_config),
    (ReportingRepositoryManager, settings.reporting_db_config),
])
```

`register_sessions` runs as an import-time side effect, so **every process that uses these
repository managers must import this module before anything tries to use them** — otherwise you'll
hit `ValueError: ... is not registered, call register_sessions() for it first.`. Don't rely on some
other module happening to import it transitively; import it explicitly, first, with a comment
explaining why:

```python
# main.py (FastAPI entrypoint)
import myapp.bootstrap  # noqa: F401  (must run before the API router is imported)

from myapp.api import api_router
...
```

The same discipline applies to any other process that uses these managers — e.g. a Celery worker
entrypoint needs the same explicit, first import, since it's a separate process with its own import
state.

### 4. Define repositories

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

`BaseRepository[Model]` works against *any* database your `RepositoryManager` is wired to, not just
the "primary" one — the model just has to be mapped as a SQLAlchemy declarative class (subclassing
FastStack's `Base`). Use it for a reporting-database table too if that table happens to have a model;
reach for `ExternalBaseRepository` when you want to query without maintaining a mapped model at all.

### 5. Define services that depend on one or more repository managers

A `BaseService` subclass declares the repository managers (and/or other services) it needs as
constructor parameters, typed by the manager class. FastStack's DI resolves and injects them. A
service isn't limited to one manager — depend on as many as the use case needs:

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
        self.reporting.get(ReportingRepository).save(orders)
```

### 6. Use the service

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

### 7. Non-DI lifecycles: CLI and Celery

`load_service`/`load_repository_manager` open and cache repository managers lazily, on first use, in
a context-local cache — there's no FastAPI request to tell you when to close them, so something has
to own that scope explicitly.

**CLI** — use `ScopedTyper` in place of `typer.Typer`. It wraps every async command with
`command_scope`, which closes whatever repository managers the command ended up using once it
returns (success or exception):

```python
from faststack.cli.scoped_typer import ScopedTyper

app = ScopedTyper()


@app.command()
async def sync_orders():
    service = load_service(OrderSyncService)
    service.sync()
```

**Celery** — subclass `faststack.celery.base_task.BaseTask`; it clears stale per-task state before
each task runs and closes any repository manager sessions the task opened once it finishes (success
or failure) — the same scope `command_scope` provides for CLI commands, adapted to Celery's signal
lifecycle:

```python
from myapp.celery_app import celery_app
from faststack.celery.base_task import BaseTask


@celery_app.task(base=BaseTask)
def sync_orders_task():
    service = load_service(OrderSyncService)
    service.sync()
```

Both paths rely on the bootstrap module from step 3 having already registered your repository
managers in that process — make sure your Celery worker's entrypoint imports it explicitly (same
`# noqa: F401` import as the FastAPI entrypoint), since a worker is a separate process with its own
import state.

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

MIT — see [LICENSE](LICENSE).
