# Database

Wiring a database into a FastSpine app has four pieces, each with its own place:

1. **Settings** — connection fields + a `DBConfig` per database, on your own settings class.
2. **`RepositoryManager` classes** — one per database, all in **one file**.
3. **Registration** — a `register_sessions(...)` call that wires each manager to its `DBConfig`,
   as an import-time side effect, in its own small module.
4. **Repositories and services** — the actual data-access code, which depends on the
   `RepositoryManager` classes from step 2, not on anything from step 3.

This doc covers all four, plus how a request/service actually ends up with a working session.

## 1. Settings: one `DBConfig` per database

Group each database's connection fields on your settings class, and expose a `DBConfig` (or
`DBReadonlyConfig`, for a connection you want opened without an implicit transaction) for each one
as a property:

```python
# myapp/settings.py
from pydantic_settings import BaseSettings
from fastspine.database.engine import DBConfig, DBServices


class AppSettings(BaseSettings):
    PRIMARY_DB_NAME: str = "app"
    PRIMARY_DB_USER: str = "app_user"
    PRIMARY_DB_PASSWORD: str = ""
    PRIMARY_DB_HOST: str = "localhost"
    PRIMARY_DB_PORT: int = 5432

    @property
    def primary_db_config(self) -> DBConfig:
        return DBConfig(
            dbname=self.PRIMARY_DB_NAME,
            user=self.PRIMARY_DB_USER,
            password=self.PRIMARY_DB_PASSWORD,
            host=self.PRIMARY_DB_HOST,
            port=self.PRIMARY_DB_PORT,
            service=DBServices.ASYNC_POSTGRES,  # picks the driver + whether it's async
        )


settings = AppSettings()
```

Field-by-field details (required vs. optional, what `service`/`DBServices` controls, etc.) are in
[Configuration: Database config](configuration.md#database-config-dbconfig). There's no fixed
`DATABASE_*` field set - name these however you like; `DBConfig` only cares about the four values
you pass into it.

## 2. `RepositoryManager` classes: one file, all of them together

Each database gets its own `RepositoryManager` subclass, generic over the session type it uses
(`Session` for sync, `AsyncSession` for async):

```python
# myapp/db/sessions.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from fastspine import RepositoryManager


class PrimaryRepositoryManager(RepositoryManager[AsyncSession]):
    """Repository manager for the main application database."""


class ReportingRepositoryManager(RepositoryManager[Session]):
    """Repository manager for the reporting/warehouse database."""
```

**Put every `RepositoryManager` subclass in this one file** (call it `sessions.py`, `db.py`,
whatever you like - the filename is not a FastSpine convention, just pick one and be consistent).
Reasons this matters in practice, not just tidiness:

- Repositories and services import these classes directly (as type hints), from all over your
  codebase. One file means one obvious place to import from, instead of hunting for which module
  happens to define `ReportingRepositoryManager`.
- The registration module (step 3) needs to import all of them together anyway, to register them
  in one `register_sessions([...])` call.
- It keeps the "one `RepositoryManager` subclass = one database connection" mapping visible at a
  glance, which gets harder to audit if they're scattered.

These classes don't need a body - `pass`, or just a docstring, is normal. They exist to be a
distinct type per database connection; `RepositoryManager`'s actual behavior lives in the base
class.

## 3. Registration: `register_sessions(...)`, in its own module

A `RepositoryManager` class isn't usable until it's registered to an actual database connection.
Do that once, as an import-time side effect, in a small dedicated module:

```python
# myapp/bootstrap.py  -- "bootstrap" is just a name, not required by FastSpine; see below
from fastspine.dependencies.database import register_sessions

from myapp.db.sessions import PrimaryRepositoryManager, ReportingRepositoryManager
from myapp.settings import settings

register_sessions([
    (PrimaryRepositoryManager, settings.primary_db_config),
    (ReportingRepositoryManager, settings.reporting_db_config),
])
```

**The module name (`bootstrap.py`) is pure convention - FastSpine doesn't look for a file by that
name or import it for you.** Call it whatever fits your project; what matters is:

- It calls `register_sessions(...)` (or the singular `register_session`/`register_async_session`)
  exactly once per process.
- Every process that uses these `RepositoryManager` classes imports this module **explicitly and
  first**, before anything tries to use them - e.g. `import myapp.bootstrap  # noqa: F401` at the
  top of `main.py` (FastAPI), the CLI entrypoint (see [CLI](cli.md#what-myappbootstrap-actually-is)),
  and a Celery worker's entrypoint. Each is a separate process with its own import state, so this
  import has to happen in each of them independently - importing it in the FastAPI app's `main.py`
  does not also register it for a Celery worker.

Skipping this, or importing it too late, surfaces as `ValueError: ... is not registered, call
register_sessions() for it first.` the first time something tries to load that manager.

`register_sessions` also validates that each manager's generic session type (`Session` vs.
`AsyncSession`) matches its `DBConfig.async_mode` (derived from `service`), raising `ValueError` at
registration time - not later, at first use - if you pair, say, a `RepositoryManager[Session]`
with an `ASYNC_POSTGRES` config.

## 4. Using it: repositories and services

Everything from here on only depends on the `RepositoryManager` classes from step 2 - not on the
registration module at all (repositories/services never import `myapp.bootstrap`).

### Repositories

- **`BaseRepository[Model]`** - for a table you own and migrate (an Alembic-tracked SQLAlchemy
  model, subclassing FastSpine's declarative `Base`). Gives you `sync_get_by_id`, `sync_filter_by`,
  `sync_create`, soft-delete helpers, and their async counterparts, for free.
- **`ExternalBaseRepository`** - for querying a database you don't own/migrate, with no mapped
  model - raw SQL via `fetch_list`/`fetchone`/`fetch_dataframe`/etc.

```python
from fastspine import BaseRepository, ExternalBaseRepository
from fastspine.models.base import Base


class Order(Base):
    __tablename__ = "orders"
    # ... columns ...


class OrderRepository(BaseRepository[Order]):
    """Repository for `Order` rows in the primary database."""


class ReportingRepository(ExternalBaseRepository):
    """Repository for ad-hoc queries against the reporting database."""

    async def get_monthly_totals(self) -> list[dict]:
        return await self.afetch_list("SELECT * FROM monthly_totals")
```

A repository never constructs its own session - it always gets `db`/`profiler` injected by
whatever creates it (see below). It doesn't know or care which `RepositoryManager` it'll be used
through, either; `BaseRepository[Model]` works against *any* database connection, not just a
"primary" one, as long as the model is mapped against that connection's engine.

### Repository managers group repositories that share a connection

A `RepositoryManager` instance is what actually holds a session. Call `.get(RepoClass)` to get a
repository bound to that same session, created lazily and cached for reuse:

```python
primary = load_repository_manager(PrimaryRepositoryManager)  # or injected via Depends/service_dep
order_repo = primary.get(OrderRepository)  # db/profiler injected automatically
```

It also exposes the transaction helpers: `sync_commit`/`sync_rollback`/`sync_flush` (sync session)
and `commit`/`rollback`/`flush` (async session - raise `TypeError` if the manager's session isn't
actually an `AsyncSession`).

### Services depend on one or more repository managers

A `BaseService` subclass declares the managers (and/or other services) it needs as constructor
parameters, typed by the manager class - FastSpine's DI resolves and injects them:

```python
from fastspine import BaseService

class OrderSyncService(BaseService):
    """Syncs order data between the primary database and the reporting database."""

    def __init__(self, primary: PrimaryRepositoryManager, reporting: ReportingRepositoryManager):
        self.primary = primary
        self.reporting = reporting

    async def sync(self):
        orders = await self.primary.get(OrderRepository).filter_by()
        self.reporting.get(ReportingRepository).save(orders)
```

Inject it into a FastAPI route with `Depends(service_dep(OrderSyncService))`, or build it eagerly
outside a request (CLI, Celery) with `load_service(OrderSyncService)` - both resolve the same
constructor dependencies, just at different times. See the
[README](../README.md#6-use-the-service) for the full DI picture, and [CLI](cli.md) /
`fastspine.celery.base_task.BaseTask` for how sessions opened this way get closed outside a
FastAPI request.
