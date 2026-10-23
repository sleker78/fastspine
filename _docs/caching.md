# Caching

FastSpine's cache layer (`fastspine.cache`) is built on Redis, with three usage levels:

1. **Decorators** (`cache_response`, `cache_method`, `cache_method_async`) — cache a function's
   return value across calls. The usual entry point.
2. **`CacheService`** — cache/fetch a single `CachableModel` instance by its own identity, with a
   read-through `fetch_cache` helper for stampede-safe lazy loading.
3. **`fastspine.cache.redis_cache`** — the low-level `cache_get`/`cache_set`/`cache_delete`/`lock`
   functions everything above is built on. Reach for these directly only if the two levels above
   don't fit.

All three levels share one on/off switch and one connection target - see
[Configuration: Cache settings](configuration.md#cache-settings). When `CACHE_ENABLED` is `False`,
or during a Redis outage once a request is already past the `CacheError`-wrapping `try`, every
level here degrades to "just call the underlying function" rather than raising.

## Running Redis locally

FastSpine already depends on `redis` (the Python client) - there's nothing extra to install on the
Python side. You just need a Redis *server* reachable at whatever `REDIS_HOST`/`REDIS_PORT` you
configure. For local development, the quickest way is Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

Then point your settings at it:

```python
REDIS_HOST = "localhost"
REDIS_PORT = 6379
CACHE_ENABLED = True
```

That's it - no extra setup, no schema/migrations, nothing to register. Once those settings are in
place, every decorator and `CacheService` method in this doc works as described. If you don't have
a Redis instance available (or set `CACHE_ENABLED=False`), everything degrades gracefully to
"never cache" rather than failing, so local development without Docker still works, just without
caching.

## Connection

`fastspine.redis.client.get_redis_client()`/`get_sync_redis_client()` build the Redis clients
(async and sync respectively) that everything else uses, from `CacheSettings.get_redis_url()` - i.e. the
`REDIS_USER`/`REDIS_PASSWORD`/`REDIS_HOST`/`REDIS_PORT` fields, not `CELERY_BROKER_URI`. This is
intentionally a separate connection target from Celery's broker (see the note in
[Configuration](configuration.md#cache-settings)) - point both at the same Redis instance if you
only want to run one. Both getters are `@lru_cache`d and return `None` when `CACHE_ENABLED` is
`False`.

Constructing a client (`Redis.from_url(...)`) never touches the network - it's lazy, like all of
redis-py. A Redis outage only ever surfaces at the point something is actually sent (`.get()`,
`.set()`, lock `.acquire()`, ...), as a `redis.exceptions.RedisError`.

## Decorators

| Decorator | For | Encoder | Key built from |
|---|---|---|---|
| `cache_response` | FastAPI route handlers (async only) | `CacheResponseEncoder` (JSON) | request path/query params, via `KeyBuilder.request_key_builder` |
| `cache_method_async` | Any async function/method | `PickledEncoder` (pickle) | function args/kwargs, via `KeyBuilder.key_builder` |
| `cache_method` | Any sync function/method | `PickledEncoder` (pickle) | function args/kwargs, via `KeyBuilder.key_builder` |

```python
from fastspine import cache_method_async

class ReviewerService:
    @cache_method_async(expire=timedelta(minutes=10))
    async def get_reviewer_stats(self, reviewer_id: int) -> ReviewerStats:
        ...
```

Common constructor parameters:

- **`expire`** (`int | timedelta`, default `60`) — TTL in seconds (or a `timedelta`). `0` or
  negative stores the key with no expiration (`SET` instead of `SETEX`).
- **`version`** (`str`, default `"v1"`) and **`key_prefix`** (`str`, default `"cache"`) — both are
  mixed into the cache key (`{key_prefix}:{version}:...`). Bump `version` when a function's return
  shape changes, so old cached values (in the old shape) stop being returned instead of crashing a
  caller that expects the new one. `key_prefix` namespaces otherwise-identical keys apart - two
  decorated functions in different modules never collide anyway (the key also includes
  `func.__module__`/`func.__name__`), so `key_prefix` mainly matters when you want to be able to
  invalidate/flush a whole group of keys by prefix from outside the decorator (e.g. `redis-cli
  --scan --pattern 'reviewers:v2:*'`).
- **`ignore_errors`** (`bool`, default `True`) — on a `CacheError` (decode failure, Redis error
  during get/set), fall back to calling the wrapped function directly when `True`; re-raise as
  `HTTPException(500)` when `False`.
- **`use_compression`** (`cache_method`/`cache_method_async` only, default `False`) — gzip the
  pickled payload before storing. Worth it for large results; adds CPU cost for small ones.
- **`log_cache_hits` / `log_cache_misses` / `log_cache_errors`** (`cache_method_async` only,
  default `False`) — emit profiler log entries (via `fetch_profiler()`) on each outcome.

`cache_response`-specific behavior:

- Requires a FastAPI `Request` to already be set in context (`ctxpool.get("request_context")` -
  `RequestMiddleware` sets this per-request). Raises `RuntimeError` if there isn't one.
- Only applies to `GET` requests; any other method raises `HTTPException(405)`.
- A request header `X-Cache-Bypass: true` forces a fresh call and refreshes the cached value,
  without reading the existing cache entry.

`cache_method`/`cache_method_async`-specific behavior:

- The key includes every positional/keyword argument the call was made with, **except** a leading
  `self`/`cls` - detected from the decorated function's own signature (its first parameter name),
  not from the argument's runtime type. So `@cache_method_async()` on an instance method caches
  per-instance-method-call correctly (two different argument values produce two different keys;
  two different instances called with the same arguments share a key, since `self` isn't part of
  it). Applying these decorators to a plain function (not a method) includes every argument.

### Locking (cache-stampede prevention)

Every decorator takes a Redis lock (`lock(cache_key)`/`sync_lock(cache_key)`, keyed as
`lock:{cache_key}`) before computing a miss, re-checks the cache once the lock is held, and only
then calls the wrapped function - so a burst of concurrent requests for the same uncached key runs
the expensive function once, not once per concurrent caller. If the lock can't be acquired, the
decorator raises `RuntimeError("Failed to acquire Redis lock")` (caught and handled the same way
as any other `CacheError`-flavored failure via `ignore_errors`).

When caching is disabled (`CACHE_ENABLED=False` or no Redis configured), `lock(...)` returns
`None` and every decorator skips straight to calling the wrapped function - no lock, no cache
lookup.

### If caching the result fails after the function already ran

If the function call succeeds but the subsequent cache-write (`cache_set`/`sync_cache_set`) raises
`CacheError`, the decorator returns the **already-computed** result - it does not call the wrapped
function a second time just because caching it failed. (A naive implementation might re-call the
function in the `except` block without realizing it already has the answer; watch for this if you
modify these decorators.)

## `CacheService` and `CachableModel`

For caching a single object by its own identity rather than by a function call, make it a
`CachableModel`:

```python
from fastspine.cache.cache_model import CachableModel

class ReviewerProfile(CachableModel):
    reviewer_id: int
    name: str

    def get_cache_identifier(self) -> str:
        return str(self.reviewer_id)

    def get_cache_expire_seconds(self) -> int:
        return 3600  # 0 = no expiration
```

`CacheService` (`fastspine.cache.cache_service.CacheService`) then gives you:

- **`set(instance)` / `sync_set(instance)`** — cache the instance under a key derived from its
  class name + `get_cache_identifier()` (via `KeyBuilder.model_key_builder`).
- **`get(plain_key, cls)` / `sync_get(plain_key, cls)`** — look up by a plain string key you choose
  (scoped by `cls.__name__`), not by an instance.
- **`delete_cache(instance)` / `sync_delete_cache(instance)`** — remove the cached entry for an
  instance.
- **`fetch_cache(instance, provider, expiration=None)`** (async only) — the read-through pattern:
  return the cached value if present; otherwise take the stampede-prevention lock, call
  `provider()` (an async zero-arg callable), cache what it returns, and return that. `expiration`
  overrides `instance.get_cache_expire_seconds()` for this call if given.

```python
async def get_profile(reviewer_id: int) -> ReviewerProfile:
    placeholder = ReviewerProfile(reviewer_id=reviewer_id, name="")
    return await CacheService.fetch_cache(placeholder, lambda: load_profile_from_db(reviewer_id))
```

All of `CacheService`'s methods use `PickledEncoder`, so cached values can be any picklable
object - not just the `CachableModel` instance itself (`fetch_cache`'s `provider` can return
anything).

## Encoders

`fastspine.cache.cache_encoder.Encoder` is the `encode`/`decode` protocol every cache function
takes a `decoder=`/`encoder=` for. Two implementations ship with FastSpine:

- **`PickledEncoder`** (the default everywhere except `cache_response`) — `pickle.dumps`/`.loads`.
  Handles arbitrary Python objects (ORM instances, dataclasses, Pydantic models, ...).
- **`CacheResponseEncoder`** — JSON via `json.dumps`/`.loads`, with a `BaseModel`/`list[BaseModel]`
  special case that calls `.model_dump()` first. Used by `cache_response` because the cached value
  must already be something FastAPI could've returned as a JSON response.

Write your own by implementing `encode(value) -> Any` / `decode(encoded) -> Any` as staticmethods -
no base class required (`Encoder` is a `typing.Protocol`).

## Errors

Every cache function wraps Redis/decode failures in `fastspine.cache.cache_exception.CacheError`:

- `redis.exceptions.RedisError` (connection issues, etc.) during any Redis call.
- `json.JSONDecodeError` / `ValueError` (the latter covers `PickledEncoder.decode`'s own
  unpickling-failure wrapping) during `cache_get`/`sync_cache_get`.

The decorators catch `CacheError` and decide what to do based on `ignore_errors`; `CacheService`'s
methods re-raise it as `CacheError` too, with no `ignore_errors` option - callers decide how to
handle it themselves.

## Low-level functions (`fastspine.cache.redis_cache`)

Only reach for these directly if you're not using a decorator or `CacheService`.

| Async | Sync | Notes |
|---|---|---|
| `cache_get(key, decoder, use_compression=False)` | `sync_cache_get(...)` | Returns `None` on a miss or when caching is disabled. |
| `cache_set(key, value, expire=60, encoder, use_compression=False)` | `sync_cache_set(...)` | Returns `False` (not an exception) if `value is None` - `None` is never cached. |
| `cache_delete(key)` | `sync_cache_delete(key)` | Returns whether a key actually existed. |
| `cache_size(key)` | `sync_cache_size(key)` | Wraps Redis `MEMORY USAGE`; `0` if the key doesn't exist or caching is disabled. |
| `lock(cache_key)` | `sync_lock(cache_key)` | Returns a redis-py `Lock` (keyed `lock:{cache_key}`), or `None` if caching is disabled. Caller is responsible for `acquire()`/`release()`. |

`use_compression=True` gzips the encoded payload before writing, and gunzips it before decoding -
set it consistently between the `cache_set` and `cache_get` call for the same key, since a value
written compressed won't decode correctly if you later read it with `use_compression=False` (or
vice versa).
