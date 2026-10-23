# Configuration

FastSpine configuration has two independent parts:

1. **`CoreSettings`** — framework-wide settings (app, cache, Celery, mailer, profiler). Populated
   once at startup from your own `pydantic_settings.BaseSettings` subclass.
2. **`DBConfig`** — one object per database connection, built from whatever fields you put on your
   own settings class. Not part of `CoreSettings` — see [Database config](#database-config-dbconfig)
   below.

## How `CoreSettings` gets populated

`CoreSettings` is **not** a `pydantic_settings.BaseSettings` itself — it's a plain class that
mirrors field names from one, copying values over field by field. You bring your own
`BaseSettings` subclass (env vars, `.env` file, whatever pydantic-settings supports), and
initialize `CoreSettings` from it once, at process startup:

```python
from pydantic_settings import BaseSettings
from fastspine.settings import init_core_settings


class AppSettings(BaseSettings):
    PROJECT_NAME: str = "My App"
    DEBUG_MODE: bool = False
    # ... every other field below, with whatever defaults/env bindings you need ...


init_core_settings(AppSettings())
```

After that, any code in the process calls `get_core_settings()` to read it back:

```python
from fastspine.settings import get_core_settings

settings = get_core_settings()
if settings.DEBUG_MODE:
    ...
```

`get_core_settings()` raises `RuntimeError("CoreSettings is not initialized")` if nothing called
`init_core_settings()` first in that process — every process that uses FastSpine (the FastAPI app,
a Celery worker, a CLI command) needs its own `init_core_settings()` call, for the same reason the
[README](../README.md#3-define-a-repositorymanager-per-database-and-register-it-via-a-dedicated-bootstrap-module)
says repository manager registration needs one per process.

**Every field below is required on your `BaseSettings` subclass unless its type includes `| None`.**
`CoreSettings.__init__` walks every field it declares and pulls the matching one off the
`BaseSettings` instance you pass in; if a non-`Optional` field is missing, it raises
`RuntimeError(f"Missing required setting: {key}")` immediately at startup — not a silent fallback
to the value shown below. The "Default" column is what `CoreSettings` itself falls back to **only**
when you call `CoreSettings()` with no `settings` argument at all (e.g. in a test), not when a
field is merely absent from an otherwise-provided `BaseSettings`.

## App settings

| Field | Type | Default | Description |
|---|---|---|---|
| `DEBUG_MODE` | `bool` | `False` | Enables debug-only behavior: `DebugUtil.debug(...)` only prints when this is `True`; `FastSpineApp`'s streaming-middleware incompatibility check only runs when this is `True`. |
| `PROJECT_NAME` | `str` | `"FastSpineLib Application::Change me in production"` | Used as the FastAPI app title by `FastSpineApp`/`run_fast_core_app` when you don't pass your own `title=`. |

## Cache settings

Redis connection details plus the global cache on/off switch. Used by `fastspine.cache` (the
`cache_response`/`cache_method`/`cache_method_async` decorators and the lower-level
`fastspine.cache.redis_cache` functions) and by `fastspine.redis.client`. See
[Caching](caching.md) for how these fields are actually used.

| Field | Type | Default | Description |
|---|---|---|---|
| `REDIS_USER` | `str` | `""` | Redis username, used by `CacheSettings.get_redis_url()`. |
| `REDIS_PASSWORD` | `str` | `""` | Redis password, used by `CacheSettings.get_redis_url()`. |
| `REDIS_HOST` | `str` | `"localhost"` | Redis host, used by `CacheSettings.get_redis_url()`. |
| `REDIS_PORT` | `int` | `6379` | Redis port, used by `CacheSettings.get_redis_url()`. |
| `CACHE_ENABLED` | `bool` | `True` | Global cache on/off switch. When `False`, `get_redis_client()`/`get_sync_redis_client()` return `None`, and every cache helper degrades to a no-op (cache miss on read, no-op on write) instead of touching Redis. |
| `CACHE_KEY_PREFIX` | `str \| None` | `None` | Prefix used when building Celery task dedupe keys in `BaseTask.generate_unique_task_id`. Not used by the `fastspine.cache` decorators themselves (they build their own keys via `KeyBuilder`). |
| `CACHED_DISABLED_USERS` | `list[str]` | `[]` | Email addresses for which caching is force-disabled, checked by `set_cache_enabled(user_email)` (wired up by `RequestMiddleware`, keyed off the authenticated user). |

**Note:** `CacheSettings.get_redis_url()` builds a `redis://user:password@host:port` URL from the four
`REDIS_*` fields above - this is what `fastspine.redis.client.get_redis_client`/
`get_sync_redis_client` actually connect to. It's intentionally separate from `CELERY_BROKER_URI`
(below): caching and Celery's broker can point at the same Redis instance or two different ones,
your choice. If you only run one Redis instance for both, set `REDIS_HOST`/`REDIS_PORT`/etc. *and*
`CELERY_BROKER_URI` to point at it.

## Celery settings

| Field | Type | Default | Description |
|---|---|---|---|
| `CELERY_BROKER_URI` | `str` | `""` | Celery broker connection URL. Only used by Celery (`fastspine.celery.engine`) - the cache layer connects via `CacheSettings.get_redis_url()`/`REDIS_*` (above) instead, not this field. Must be a `redis://`, `rediss://`, or `unix://` URL (empty string fails to parse). |
| `CELERY_BACKEND_URI` | `str` | `"redis://localhost:6385/0"` | Celery result backend URL. |
| `CELERY_RESULT_EXPIRES` | `int` | `604800` (7 days, in seconds) | How long Celery keeps task results around. |
| `CELERY_MAIN_NAME` | `str` | `"_redis_main"` | Name of the main Celery app instance. |
| `CELERY_TASK_FOLDERS` | `list[str]` | `[]` | Module paths Celery should autodiscover tasks from. |
| `WORKERS_ON` | `bool` | `True` | Whether Celery workers are enabled for this deployment. |
| `VISIBILITY_TIMEOUT` | `int` | `3600` | Default visibility timeout (seconds) for in-flight tasks. |

## Profiler settings

Control `fastspine.lib.profiler.Profiler`, as constructed by `load_profiler()`/`fetch_profiler()`
(`fastspine.dependencies.profiler`).

| Field | Type | Default | Description |
|---|---|---|---|
| `PROFILER_NAME` | `str \| None` | `None` | Name tag attached to profiler log entries. |
| `PROFILER_ENABLED` | `bool \| None` | `False` | Whether `Profiler.log`/`.debug`/`.info`/`.warning`/`.error` actually emit anything. When falsy, every log call is a no-op. |
| `PROFILER_LOG_LEVEL` | `int` | `logging.INFO` | Logging level the profiler's `log()` calls use by default. |
| `PROFILER_TRACK_MEMORY` | `bool \| None` | `False` | Whether the profiler also records process memory usage (via `psutil`) alongside timing. |

## Mailer settings

Passed straight through to `fastapi-mail`'s `ConnectionConfig` by `fastspine.mailer`. See
[fastapi-mail's docs](https://sabuhish.github.io/fastapi-mail/) for what each field controls.

| Field | Type | Default |
|---|---|---|
| `MAIL_USERNAME` | `str \| None` | `None` |
| `MAIL_PASSWORD` | `str \| None` | `None` |
| `MAIL_FROM` | `str \| None` | `None` |
| `MAIL_PORT` | `int \| None` | `None` |
| `MAIL_SERVER` | `str \| None` | `None` |
| `MAIL_STARTTLS` | `bool \| None` | `None` |
| `MAIL_SSL_TLS` | `bool \| None` | `None` |
| `USE_CREDENTIALS` | `bool \| None` | `None` |
| `VALIDATE_CERTS` | `bool \| None` | `None` |

All nine are typed `| None`, so `CoreSettings` won't raise if your `BaseSettings` subclass omits
them entirely — but `fastspine.mailer` will fail at the point it actually tries to send mail if the
required ones (server, port, credentials) were never set.

## Logging/printing settings as-is

`CoreSettings` mixes in `RepresentableMixin`, which gives it a plain `__repr__`/`__str__` that
dumps every instance attribute (`REDIS_PASSWORD`, `MAIL_PASSWORD`, etc. included) as plain text.
There's no secret-masking. Don't `print()`/log a `CoreSettings` instance directly in a context
that gets captured (error trackers, access logs, etc.).

## Database config (`DBConfig`)

Separate from `CoreSettings`. Each database your app talks to gets its own `DBConfig` (or
`DBReadonlyConfig`), built from whatever fields you choose to put on your settings class — there's
no fixed `DATABASE_*` field set. See the
[README, step 2](../README.md#2-configure-settings-with-a-dbconfig-per-database) for the pattern
(group fields per database, expose a `@property` returning a `DBConfig`), and step 3 for how
`DBConfig` instances get wired to `RepositoryManager` subclasses via `register_sessions`.

`fastspine.database.engine.DBConfig` fields:

| Field | Type | Default | Description |
|---|---|---|---|
| `dbname` | `str` | *required* | Database name. |
| `user` | `str` | *required* | Database user. |
| `password` | `SecretStr \| None` | `None` | Database password. Must be set to build a connection URL (`connection_url()`/`db_url()` raise `TypeError` otherwise). |
| `host` | `str` | *required* | Database host. |
| `port` | `int` | *required* | Database port. Must be in `1..65535`. |
| `service` | `DBServices` | `DBServices.POSTGRES` | Which driver/dialect to use - see below. Also determines `async_mode`. |
| `async_mode` | `bool` | derived from `service` | Set automatically in `model_post_init`; don't set it directly - pick the right `service` instead. |
| `autocommit` | `bool` | `False` (`True` on `DBReadonlyConfig`) | Passed through to the async engine's isolation level when `async_mode` is `True`. |

`DBServices` values and the driver each maps to:

| `DBServices` member | Driver | `async_mode` |
|---|---|---|
| `POSTGRES` | `postgresql+psycopg2` | `False` |
| `ASYNC_POSTGRES` | `postgresql+asyncpg` | `True` |
| `MYSQL` | `mysql+pymysql` | `False` |
| `ASYNC_MYSQL` | `mysql+aiomysql` | `True` |

`DBReadonlyConfig` is identical to `DBConfig` except its `autocommit` default is `True` instead of
`False` - use it for read-replica/reporting connections where you don't want implicit transactions
held open.

The `service` you pick must match the session type (`Session` vs. `AsyncSession`) the
corresponding `RepositoryManager` subclass is generic over - `register_sessions` validates this
and raises `ValueError` on a mismatch (e.g. a `RepositoryManager[Session]` paired with an
`ASYNC_POSTGRES` config).
