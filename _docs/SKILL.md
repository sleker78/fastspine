---
name: fastspine
description: Use when writing or reviewing code in a project that depends on the fastspine package (imports from `fastspine`, has a `RepositoryManager`/`BaseService`/`BaseRepository` subclass, or a `myapp/bootstrap.py`-style registration module) - covers the service-repository/DI pattern, the per-process bootstrap discipline, required settings, and the most common runtime errors this framework produces.
---

# FastSpine

FastSpine is a FastAPI-based service-repository framework: `RepositoryManager` (one per
database) → `BaseRepository[Model]`/`ExternalBaseRepository` (data access) → `BaseService`
(business logic), resolved via `Service[T]` in FastAPI routes or `load_service(T)` everywhere
else (CLI, Celery, scripts). It also provides Redis caching decorators, a Celery `BaseTask` base
class, and a `ScopedTyper` CLI base.

**This file is a condensed, gotcha-focused cheat sheet.** The full prose docs live in the
`fastspine` repo's `_docs/*.md` (configuration, database, caching, cli, celery, example) - read
those for the "why", this file for "what will break and how to avoid it."

## Installing

`import fastspine` itself needs nothing beyond fastspine's core deps (fastapi, sqlalchemy,
pydantic, ...). Everything else is an opt-in extra - install only what the app actually uses:

```bash
pip install "fastspine[postgres,redis]"       # e.g. async Postgres + caching, no Celery
pip install "fastspine[postgres,redis,celery,cli]"  # or all = everything
```

| Extra | Unlocks |
|---|---|
| `postgres` | `DBServices.POSTGRES`/`ASYNC_POSTGRES` |
| `mysql` | `DBServices.MYSQL`/`ASYNC_MYSQL` |
| `redis` | `fastspine.cache` (decorators, `CacheService`) |
| `celery` | `fastspine.celery` (`BaseTask`, `get_celery_instance`) - also pulls in `redis` |
| `mailer` | `fastspine.mailer` |
| `cli` | `fastspine.cli.scoped_typer` |

`BaseTask` and the cache decorators are **not** top-level exports (they'd force every consumer to
have `celery`/`redis` installed just to `import fastspine`). Import them from their submodule:

```python
from fastspine.celery.base_task import BaseTask
from fastspine.cache.cache_decorater import cache_method_async, cache_method, cache_response
```

## The one rule that causes 90% of confusing errors

**Every process that uses FastSpine (the FastAPI app, a CLI command, a Celery worker, a one-off
script) must, as the very first import, trigger a module that calls both `init_core_settings()`
and `register_sessions()`.** Each process has its own import state - importing that module in one
process does not register anything in another. Convention: put both calls in one small module
(commonly `myapp/bootstrap.py`, but the name is not a FastSpine requirement) and import it first,
with a `noqa: F401` comment explaining why:

```python
# myapp/bootstrap.py
from fastspine.dependencies.database import register_sessions
from fastspine.settings import init_core_settings

from myapp.db.sessions import PrimaryRepositoryManager
from myapp.settings import settings

init_core_settings(settings=settings)   # only needed explicitly for CLI/Celery - FastSpineApp
                                         # does this for you in the FastAPI process (see below)

register_sessions([
    (PrimaryRepositoryManager, settings.primary_db_config),
])
```

```python
# main.py / cli/main.py / celery_app.py - the FIRST import, before anything else
import myapp.bootstrap  # noqa: F401  (must run before any route/command/task uses a service)
```

`FastSpineApp(settings=settings)` calls `init_core_settings()` internally, so the FastAPI process
doesn't need the explicit call (but still needs `register_sessions()`, so still needs the
bootstrap import). CLI and Celery processes need both, since neither constructs a `FastSpineApp`.

## Settings: `CoreSettings` requires fields you might never use

Your own `pydantic_settings.BaseSettings` subclass must declare **every field that's not typed
`| None`** across *all* of `CoreSettings`'s groups (app, cache, celery, profiler) - not just the
ones your app actually uses. Skipping Celery entirely still means you need Celery's required
fields declared (with harmless defaults), or `init_core_settings`/`FastSpineApp(...)` raises
`RuntimeError: Missing required setting: X` at startup. Mailer's fields are all `| None` - safe to
omit.

Known-safe starter block to copy into any new app's settings class (adjust DB_*/REDIS_* for real
use; everything else can stay as shown if that feature isn't used):

```python
from pydantic_settings import BaseSettings

class AppSettings(BaseSettings):
    PROJECT_NAME: str = "My App"
    DEBUG_MODE: bool = False

    # Cache (own connection, separate from Celery's broker - see below)
    CACHE_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USER: str = ""
    REDIS_PASSWORD: str = ""
    CACHED_DISABLED_USERS: list[str] = []

    # Celery - required even if you don't use Celery at all
    CELERY_RESULT_EXPIRES: int = 7 * 24 * 60 * 60
    CELERY_BROKER_URI: str = ""
    CELERY_BACKEND_URI: str = "redis://localhost:6385/0"
    CELERY_MAIN_NAME: str = "_redis_main"
    CELERY_TASK_FOLDERS: list[str] = []
    WORKERS_ON: bool = False
    VISIBILITY_TIMEOUT: int = 3600
    CELERY_DEDUPLICATION_ENABLED: bool = True

    # Profiler - only PROFILER_LOG_LEVEL is non-Optional
    PROFILER_LOG_LEVEL: int = 20  # logging.INFO
```

`CacheSettings` (`REDIS_HOST`/`PORT`/`USER`/`PASSWORD`) and `CelerySettings.CELERY_BROKER_URI` are
**intentionally separate connections** - caching does not read `CELERY_BROKER_URI`, even if you
point both at the same Redis instance in practice. Don't conflate them.

## Dependency injection

Two parallel paths, same constructor-dependency resolution, different trigger:

- **FastAPI routes**: `Service[YourService]` (`from fastspine import Service`) - shorthand for
  `Annotated[YourService, Depends(service_dep(YourService))]`. Use it directly as a parameter
  type, no `Annotated`/`Depends` import needed.
- **Everywhere else** (CLI commands, Celery tasks, scripts): `load_service(YourService)` -
  resolves the same dependency graph eagerly.

**Gotcha**: a `BaseService`/`BaseRepository` subclass must define its own `__init__` with
annotated parameters - even `def __init__(self): pass` if it needs nothing. Without one, DI falls
back to inspecting `object.__init__(*args, **kwargs)` and raises `ValueError: Parameter 'args' ...
is missing a type annotation`. Constructor params typed as another `BaseService` subclass or a
`RepositoryManager` subclass get resolved automatically (nested); anything else needs its own
default value or DI raises `ValueError: Unsupported dependency type ...`.

```python
class OrderService(BaseService):
    def __init__(self, db: PrimaryRepositoryManager, mailer: MailerService):  # both auto-resolved
        self.db = db
        self.mailer = mailer
```

## Database

- One `RepositoryManager[Session]` (sync) or `RepositoryManager[AsyncSession]` (async) subclass
  per database connection - put every one in the same file, registered together via
  `register_sessions([(ManagerClass, db_config), ...])`.
- `BaseRepository[Model]` for your own mapped models (subclass `fastspine.models.base.Base`,
  which already declares `id` - don't redeclare it); `ExternalBaseRepository` for raw-SQL access
  to data you don't own.
- Method naming: **async** repos get `get_by_id`/`filter_by`/`filter_one_by`/`create(instance,
  flush=True, commit=False)`/`delete(instance, commit=True)`/`commit()`; **sync** repos get the
  same names prefixed `sync_` (`sync_get_by_id`, `sync_create`, ...). `create`/`sync_create` take
  an already-constructed model *instance*, not kwargs.
- `fastspine.mixins`: `CreatedAtMixin`/`UpdatedAtMixin`/`TimestampMixin`/`SoftDeleteMixin` -
  `class MyModel(Base, CreatedAtMixin): ...` (Base first in the MRO).
- `manager.get(RepoClass)` returns a repo bound to that manager's session, cached per-manager-
  instance - don't construct repositories directly.

## Caching

```python
from fastspine.cache.cache_decorater import cache_method_async

class MyService(BaseService):
    @cache_method_async(expire=timedelta(minutes=5))  # or expire=<seconds:int>
    async def get_thing(self, thing_id: int) -> Thing: ...
```

- Keys exclude `self`/`cls` automatically (detected from the function's own first param name) -
  caches per-call-args, not per-instance.
- No cache invalidation on write by default - it's TTL-only. If a value changes, callers see the
  old value for up to `expire` seconds. That's the intended simple model, not a bug to "fix" with
  manual invalidation unless the app specifically needs it.
- On a `CacheError` *after* the wrapped function already ran (e.g. the write to Redis fails), the
  decorator returns the already-computed result - it does not call the function a second time.

## Celery

- `BaseTask` assumes **sync** tasks (plain `def`, not `async def`) using `Session`-backed
  `RepositoryManager`s. An `AsyncSession`-backed manager used inside a sync task leaks its
  connection (logged, not crashed) - don't mix them.
- Build the app and autodiscover tasks together, eagerly, in one module:
  ```python
  # myapp/celery_app.py
  import myapp.bootstrap  # noqa: F401
  from fastspine.celery.engine import get_celery_instance
  app = get_celery_instance(settings)
  app.autodiscover_tasks(settings.CELERY_TASK_FOLDERS)
  ```
- One worker entrypoint script for both dev and prod, `argv` driven by `settings.DEBUG_MODE` -
  not two different mechanisms (`celery -A module worker` CLI vs. a dev-only script):
  ```python
  # myapp/worker_main.py
  import myapp.bootstrap  # noqa: F401
  from myapp.celery_app import app
  argv = ["worker", "--loglevel=DEBUG", "--concurrency=1"] if settings.DEBUG_MODE else \
         ["worker", f"--concurrency={settings.CONCURRENCY}"]
  app.worker_main(argv)
  ```
- `BaseTask`'s own Redis-based dedup only runs when `CELERY_BROKER_URI` is a `redis://`/
  `rediss://` URL - other brokers (RabbitMQ, ...) are assumed to handle dedup at the transport
  level, so this app-level check (and its Redis usage) is skipped entirely for them.
- Trigger tasks from a service method, not directly from a route handler (`service.trigger_x()`
  calling `.delay()` inside, not `@router.post(...) def x(): some_task.delay()`). If the task
  module lives in a separate, heavier package (its own ML/data deps) from the one calling
  `.delay()`, import the task inside the method, not at module top, to avoid pulling that whole
  package into e.g. the API process.

## CLI

`ScopedTyper` (`from fastspine.cli.scoped_typer import ScopedTyper`) wraps every `async def`
command with open-lazily/close-on-exit repository-manager scoping - plain `typer.Typer()` doesn't.
Sub-apps mounted via `add_typer()` need to be `ScopedTyper()` too; mounting a plain `typer.Typer()`
sub-app does not retroactively wrap its commands. Sync (`def`, not `async def`) commands are never
scoped - if a command uses `load_repository_manager`/`load_service`, make it `async def`.

## Profiler

`load_profiler()`/`fetch_profiler()` return a lazily-built, per-context-cached `Profiler`. To
inject a custom one (e.g. ship metrics somewhere instead of just logging), subclass `Profiler` and
register a factory - once per process, same discipline as bootstrap:

```python
from fastspine import Profiler, set_profiler_factory, FastSpineApp

class MetricsProfiler(Profiler): ...

set_profiler_factory(lambda: MetricsProfiler(name="my-app", enabled=True))
# or, for the FastAPI process specifically, inline:
app = FastSpineApp(settings=settings, profiler_factory=lambda: MetricsProfiler(enabled=True))
```

The factory must return a `Profiler` *subclass instance* - DI matches constructor params on
`param_type is Profiler` exactly, and every injection point is typed as plain `Profiler`.

## Troubleshooting: exact error → cause

| Error | Cause | Fix |
|---|---|---|
| `RuntimeError: CoreSettings is not initialized` | `get_core_settings()` called before `init_core_settings()` ran in *this* process | CLI/Celery: call `init_core_settings(settings=settings)` in your bootstrap module. FastAPI: use `FastSpineApp(settings=settings)`, not a bare `FastAPI()`. |
| `RuntimeError: Missing required setting: X` | Your `BaseSettings` subclass is missing a non-`Optional` `CoreSettings` field, even one from a feature group (Celery, Profiler) you don't use | Add the field with any valid default - see the starter block above. |
| `ValueError: ... is not registered, call register_sessions() for it first.` | A `RepositoryManager` subclass was used before `register_sessions()` ran *in this process* | Make sure your bootstrap module is the first import in this entrypoint, not just some other entrypoint. |
| `ModuleNotFoundError: No module named 'celery'/'redis'/'typer'/'fastapi_mail'` | Using a feature without its extra installed | `pip install "fastspine[celery]"` (etc.) - `import fastspine` itself doesn't need it, only the specific submodule does. |
| `ValueError: Parameter 'args' of X ... is missing a type annotation` | A `BaseService`/`BaseRepository` subclass has no explicit `__init__`, so DI inspected the inherited `object.__init__(*args, **kwargs)` | Give the class its own `__init__`, even an empty one. |
| `ValueError: Unsupported dependency type ... in service X` | A constructor param isn't another `BaseService`/`RepositoryManager` and has no default | Give it a default value, or make it one of the two supported types. |
| `TypeError: Cannot subtract offset-naive and offset-aware datetimes` (Postgres) | A `DateTime` column without `timezone=True` paired with a timezone-aware Python `datetime` default | Use `mapped_column(DateTime(timezone=True), ...)`, or use `CreatedAtMixin`/`TimestampMixin` which already do this. |
| `NotNullViolationError: null value in column "..._id"` on delete | A relationship's child rows have no delete cascade - SQLAlchemy nulls the FK instead of deleting | Add `cascade="all, delete-orphan"` to the parent-side `relationship(...)`. |

## Further reading

The fastspine repo's `_docs/` folder has the full prose version of all of the above, plus a
complete worked example (`_docs/example.md`): `configuration.md`, `database.md`, `caching.md`,
`cli.md`, `celery.md`.
