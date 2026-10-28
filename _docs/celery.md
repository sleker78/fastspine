# Celery

`fastspine.celery` provides two things:

1. **`get_celery_instance(settings)`** (`fastspine.celery.engine`) - builds a `Celery` instance
   from your settings.
2. **`BaseTask`** - a task base class that gives each task Redis-backed deduplication, automatic
   repository-manager session cleanup, and failure-fallback dispatch.

Celery settings (`CELERY_BROKER_URI`, `CELERY_BACKEND_URI`, `CELERY_TASK_FOLDERS`, ...) are
documented in [Configuration: Celery settings](configuration.md#celery-settings) - this doc
covers how they're used, not what each one means.

`celery` is an optional extra (it also pulls in `redis`, which `BaseTask` needs for dedup/caching):

```bash
pip install "fastspine[celery]"
```

`fastspine.celery.engine`/`fastspine.celery.base_task` aren't importable without it - but `import
fastspine` itself doesn't require `celery` at all, so this only matters for the process that
actually runs tasks (worker, and wherever `.delay()` is called from).

**`BaseTask` assumes sync tasks.** Its session cleanup (`fastspine.dependencies.repository_manager._close_sessions_sync`)
can only close a sync `Session`; if a task loads an `AsyncSession`-backed `RepositoryManager`, it
logs an error and leaves that session open rather than crashing (see
["Session cleanup" below](#session-cleanup-on-completionfailure)). Write tasks as plain `def`, not
`async def`, and use `Session`-based repository managers inside them. If a task genuinely needs to
await something async, call `asyncio.run(...)` yourself inside the task body.

## Setting up the app

Build the `Celery` app and run task autodiscovery **together, eagerly, at import time**, in one
small module - so that simply importing it always gives you a fully-wired app (tasks registered),
whether you're about to start a worker or just need to call `.delay()` on a task from elsewhere
(e.g. a FastAPI route enqueuing work):

```python
# myapp/celery_app.py
import myapp.bootstrap  # noqa: F401  (must run before any task uses a repository manager)

from fastspine.celery.engine import get_celery_instance

from myapp.settings import settings

app = get_celery_instance(settings)
app.autodiscover_tasks(settings.CELERY_TASK_FOLDERS)
```

`get_celery_instance(settings)`:

- Calls `init_core_settings(settings=settings)` for you - so you don't need a separate
  `init_core_settings()` call in this module, unlike the FastAPI/CLI entrypoints. (It still has to
  be *some* call in *this process* - a Celery worker is its own process, same as a CLI invocation;
  see [Database: registration](database.md#3-registration-register_sessions-in-its-own-module).)
- Builds the `Celery` app from `CELERY_MAIN_NAME`/`CELERY_BROKER_URI`/`CELERY_BACKEND_URI`/
  `CELERY_RESULT_EXPIRES`/`VISIBILITY_TIMEOUT`.

`app.autodiscover_tasks(folders)` is plain Celery - a list of package paths, one `tasks` submodule
import per package by convention (`CELERY_TASK_FOLDERS = ["myapp.jobs"]` discovers
`myapp.jobs.tasks`). Calling it here, right after building `app`, means every importer of
`myapp.celery_app` gets the same fully-registered app - the worker entrypoint below doesn't need
to repeat it, and neither does anything that just wants to enqueue a task.

The `import myapp.bootstrap` at the top is the same registration step CLI/FastAPI need - a worker
process has its own import state, so nothing else is guaranteed to register your
`RepositoryManager` classes for you here.

## Writing tasks with `BaseTask`

Opt a task into `BaseTask`'s behavior with `base=BaseTask` - it's per-task, not automatic for every
task on the app:

```python
# myapp/jobs/tasks.py
from fastspine.celery.base_task import BaseTask
from fastspine import load_service

from myapp.celery_app import app
from myapp.services.sync_service import OrderSyncService


@app.task(base=BaseTask)
def sync_orders_task():
    service = load_service(OrderSyncService)
    service.sync()
```

### Deduplication

`BaseTask.apply_async` hashes the task name + args + kwargs into a key, and skips sending the task
if that exact key is already recorded in Redis (`CACHE_KEY_PREFIX` setting prefixes the key) - so
calling `sync_orders_task.delay()` twice in a row while the first call is still pending/running
does not enqueue it twice. The key is cleared once the task finishes (success or failure) or if
`apply_async` itself raises.

**When a call is skipped as a duplicate, it returns a plain `{"status": "..."}` dict, not an
`AsyncResult`.** Code that calls `.delay()`/`.apply_async()` expecting to chain `.get()`/`.id`/etc.
off the result needs to handle that case (e.g. check `isinstance(result, dict)`) if dedup is
enabled for that task.

**This dedup logic only runs at all when `CELERY_BROKER_URI` is a Redis broker** (`redis://`/
`rediss://`, checked via `fastspine.celery.broker.is_redis_broker`). Redis has no built-in message
deduplication, which is why `BaseTask` implements it at the application level. Other brokers
(RabbitMQ, ...) typically have their own deduplication module/plugin at the transport level - for
those, `apply_async` skips this check entirely and forwards straight to Celery's own
`apply_async`, rather than requiring a working cache-Redis connection for something the broker
already handles. (This is also why `broker_transport_options`'s `visibility_timeout` - a
Redis/SQS-only transport option - is only set by `get_celery_instance` for a Redis broker too.)

When the broker *is* Redis, dedup storage itself uses the same cache-layer Redis connection as
[Caching](caching.md) (`CacheSettings`/`REDIS_HOST`/etc - not `CELERY_BROKER_URI` directly, despite
both being Redis in this case). If `CACHE_ENABLED` is `False` or that connection isn't reachable,
`get_redis_client()` returns `None` and `_cache_task_id` is a no-op - dedup is skipped, every call
goes through.

### Session cleanup on completion/failure

Signal handlers on `BaseTask` close whatever `load_repository_manager`/`load_service` opened
during the task, on both the success and failure paths (`task_postrun`/`task_failure`), and clear
stale state before the next task runs (`task_prerun`) - the same problem
[`command_scope` solves for CLI commands](cli.md#what-actually-happens), adapted to Celery's
signal-based lifecycle instead of a single `with` block.

If a task loaded an `AsyncSession`-backed manager, cleanup logs
`"Cannot close an AsyncSession from a sync scope; the connection will leak."` and moves on, rather
than raising - which is exactly what it says: that connection leaks. Don't mix async repository
managers into `BaseTask`-based tasks.

### Failure fallback

On `task_failure`, `BaseTask` looks for a function named `{task_function_name}__fallback` in the
same module as the failed task, and calls it with the same `args`/`kwargs` if found:

```python
@app.task(base=BaseTask)
def sync_orders_task():
    ...

def sync_orders_task__fallback():
    """Called automatically if `sync_orders_task` raises."""
    notify_ops_channel("Order sync failed - check logs.")
```

No fallback function defined is not an error - it's just skipped (logged at debug level).

## Triggering a task

Import the task and call `.delay()` (or `.apply_async()` for explicit `countdown`/`eta`/queue
routing). Same as the rest of the service-repository pattern, a route shouldn't call `.delay()`
itself - it calls a service method, and the service is what knows it needs to enqueue a task:

```python
# myapp/services/sync_service.py
from fastspine import BaseService


class OrderSyncService(BaseService):
    def trigger_sync(self) -> None:
        from myapp.jobs.tasks import sync_orders_task

        sync_orders_task.delay()

    def trigger_sync_for(self, reviewer_id: int) -> None:
        from myapp.jobs.tasks import sync_orders_task

        # with arguments, and an explicit delay instead of "now"
        sync_orders_task.apply_async(args=(reviewer_id,), countdown=30)
```

**Import the task inside the method, not at module top**, if `myapp.jobs.tasks` (or whatever
package actually defines your tasks) is a separate, heavier package from the one calling
`.delay()` - e.g. the worker lives in its own package with its own dependencies (ML libraries,
data processing, etc.) that the API process has no other reason to import. A top-level `from
myapp.jobs.tasks import sync_orders_task` would force importing that entire package - and
everything it transitively imports - just to get a reference to one task, every time this service
module is imported. A local import inside the method defers that cost to the one call path that
actually needs it, and avoids a circular import if the worker package ever needs to import
anything from the API/service side. If tasks live in the same lightweight package as everything
else, a normal top-level import is fine - this is about avoiding an unnecessary cross-package
import, not a blanket rule.

```python
# myapp/api/orders.py
from typing import Annotated

from fastapi import APIRouter, Depends

from fastspine import service_dep

from myapp.services.sync_service import OrderSyncService

router = APIRouter()

OrderSyncServiceDep = Annotated[OrderSyncService, Depends(service_dep(OrderSyncService))]


@router.post("/orders/sync")
def trigger_sync(service: OrderSyncServiceDep):
    service.trigger_sync()
    return {"status": "queued"}
```

The task is still just a plain Celery task underneath, so calling `.delay()` directly from a route
also works, with no service in between:

```python
@router.post("/orders/sync")
def trigger_sync():
    sync_orders_task.delay()
    return {"status": "queued"}
```

...but prefer the service-based version above for anything beyond a trivial example - it keeps the
route a thin transport layer and the decision to enqueue a task (and whatever logic decides which
task, with which arguments) inside the service, consistent with the rest of this pattern.

Since `sync_orders_task` uses `base=BaseTask`, `.delay()`/`.apply_async()` goes through
`BaseTask.apply_async` first - see [Deduplication](#deduplication) above for what you get back
when a duplicate call is skipped.

Enqueuing only needs a broker connection, not a running worker in the same process - whatever
process makes this call (here, the FastAPI process) only needs `myapp.jobs.tasks` (and
transitively `myapp.celery_app`) importable. It does **not** need to be the worker process, and
it does not start a worker as a side effect of importing `app`.

## Running the worker

Use **one** entrypoint script for both dev and prod - don't maintain two different mechanisms
(e.g. a plain script for dev vs. the `celery` CLI for prod). The only thing that should differ
between environments is what `argv` gets built from a settings flag, same as any other
environment-dependent behavior in the app:

```python
# myapp/worker_main.py
import myapp.bootstrap  # noqa: F401  (must run before the celery_app import below)

from myapp.celery_app import app
from myapp.settings import settings

if __name__ == "__main__":
    argv = ["worker"]
    if settings.DEBUG_MODE:
        argv += ["--loglevel=DEBUG", "--concurrency=1"]
    else:
        argv += [f"--concurrency={settings.CONCURRENCY}"]

    app.worker_main(argv)
```

```bash
python myapp/worker_main.py
```

Run this exact script, unmodified, in both environments - a local dev `.env` sets `DEBUG_MODE=True`
(a field already on FastSpine's `AppSettings`, so `settings.DEBUG_MODE` works out of the box),
which forces `--concurrency=1` so a single task runs at a time and is easy to step through in a
debugger. A prod deployment sets `DEBUG_MODE=False` and a real `CONCURRENCY` - the latter isn't a
FastSpine field, it's just a plain `int` setting you add to your own settings class, sourced the
same way the rest of your settings are (env vars/config map) - **set it to more than `1`** in
prod: with the default prefork pool, `--concurrency=N` runs `N` worker child processes pulling
from the same queue, so `1` leaves you with no parallelism at all (every task waits for the
previous one to finish, regardless of how many broker messages are queued up). A reasonable
starting point is your container's CPU count (Celery defaults to `multiprocessing.cpu_count()`
when `--concurrency` is omitted entirely) and tune it from there based on whether your tasks are
CPU-bound or mostly waiting on I/O (DB calls, external APIs) - I/O-bound tasks can often run higher
concurrency than CPU count without contention. There is no separate `celery -A myapp.celery_app
worker` CLI invocation to keep in sync with this script - `app.worker_main(argv)` *is* that CLI,
called in-process with the same `argv` it would otherwise parse from `sys.argv`.

Because `myapp/celery_app.py` already calls `autodiscover_tasks` eagerly at import time (see
above), importing `app` from it here is enough - this script doesn't need to repeat that call.

`fastspine.celery.engine` also exposes `run_celery_worker(settings, argv)`, which builds its own
`Celery` instance (via `get_celery_instance`), autodiscovers tasks on it, and calls `worker_main`
- all in one call. Don't reach for it once you have a module like `myapp/celery_app.py`: it builds
a *second*, separate `Celery` instance, distinct from the `app` your tasks were decorated against
with `@app.task(...)` - starting a worker on that second instance would see no tasks registered.
Calling `app.worker_main(argv)` directly on the one `app` everything else already imports, as
above, is the version of this that actually works once tasks exist in their own module.

Scale by running more worker processes/containers against the same broker - `BaseTask`'s
Redis-based deduplication (above) is what keeps concurrent workers from double-processing the same
logical task.
