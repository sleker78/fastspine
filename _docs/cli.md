# CLI

`fastspine.cli.scoped_typer` gives CLI commands (built on [Typer](https://typer.tiangolo.com/))
the same repository-manager lifecycle that FastAPI gives a request: open sessions lazily as
they're used, close everything once the command is done - whether it succeeded or raised.

## The problem this solves

Inside a FastAPI route, `Depends()` opens a repository manager's session when a handler first
needs it and closes it after the response is sent - you never think about it. Outside of FastAPI
(a CLI command, same as a Celery task), there's no request lifecycle to hook that into.
`load_repository_manager`/`load_service` *will* open sessions lazily on first use and cache them
for reuse, but nothing closes them automatically - that's what `command_scope` is for.

## Usage

Use `ScopedTyper` in place of `typer.Typer`. Every `async def` command registered on it gets
wrapped automatically. A real CLI usually has more than one command, grouped into modules - the
pattern below (one `ScopedTyper` per command module, mounted into a top-level app) is what this
looks like in practice:

```python
# myapp/cli/commands/orders.py
from fastspine.cli.scoped_typer import ScopedTyper
from fastspine import load_service

from myapp.services.sync_service import OrderSyncService

app = ScopedTyper(help="Commands for syncing orders.")


@app.command(help="Sync orders from the upstream source.")
async def sync():
    service = load_service(OrderSyncService)
    await service.sync()
```

```python
# myapp/cli/commands/keywords.py
from fastspine.cli.scoped_typer import ScopedTyper
from fastspine import load_service

from myapp.services.keyword_service import KeywordExtractionService

app = ScopedTyper(help="Commands for extracting keywords.")


@app.command(help="Extract keywords for every item submitted since the last run.")
async def extract():
    service = load_service(KeywordExtractionService)
    await service.extract_pending()
```

```python
# myapp/cli/main.py
"""My App CLI entry point."""

import myapp.bootstrap  # noqa: F401  (must run before any command uses a repository manager)

from fastspine.cli.scoped_typer import ScopedTyper
from myapp.cli.commands import keywords, orders

app = ScopedTyper(no_args_is_help=True)

app.add_typer(orders.app, name="orders", help="Commands for syncing orders.")
app.add_typer(keywords.app, name="keywords", help="Commands for extracting keywords.")

if __name__ == "__main__":
    app()
```

Run with `python -m myapp.cli.main orders sync` / `python -m myapp.cli.main keywords extract`.
`no_args_is_help=True` on the top-level app means running it with no arguments prints the usage/
command list rather than a bare error - worth setting once you have more than a couple of command
groups.

For a single-command CLI, you don't need the `add_typer`/sub-module split - just register the
command directly on one `ScopedTyper()` and run `python -m myapp.cli` (Typer treats a single
registered command as the app's default, no subcommand name needed).

### What `myapp.bootstrap` actually is

`import myapp.bootstrap` in `main.py` isn't a FastSpine API call - it's your own small module
whose only job is registering every `RepositoryManager` with its database, as an import-time side
effect (full pattern: [README, step 3](../README.md#3-define-a-repositorymanager-per-database-and-register-it-via-a-dedicated-bootstrap-module)):

```python
# myapp/bootstrap.py
from sqlalchemy.ext.asyncio import AsyncSession

from fastspine import RepositoryManager
from fastspine.dependencies.database import register_sessions

from myapp.settings import settings


class PrimaryRepositoryManager(RepositoryManager[AsyncSession]):
    """Repository manager for the main application database."""


register_sessions([
    (PrimaryRepositoryManager, settings.primary_db_config),
])
```

`load_repository_manager`/`load_service` (used inside `orders.sync`/`keywords.extract` above) look
up their manager in a registry that `register_sessions` populates. If that registration hasn't run
yet, they raise `ValueError: ... is not registered, call register_sessions() for it first.` - the
`import myapp.bootstrap` line exists purely to force that registration to happen, exactly once,
before any command gets a chance to run.

Why it has to be imported explicitly in `main.py`, rather than relying on it happening naturally:
a CLI invocation is a fresh process with its own import state (same as a Celery worker, different
from the FastAPI app process) - nothing else in the CLI's import graph is guaranteed to import
`myapp.bootstrap` for you. `orders.py`/`keywords.py` import `fastspine`/`myapp.services.*`, not
`myapp.bootstrap` - so without the explicit import in `main.py`, the registration would simply
never happen in the CLI process, and every command would fail at the `load_repository_manager`
call with the "not registered" error above, regardless of which database it needs.

## What actually happens

`ScopedTyper.command()` checks whether the function you're registering is a coroutine function
(`inspect.iscoroutinefunction`). If it is, it wraps it with `command_scope` before handing it to
Typer; a plain `def` command is registered as-is.

`command_scope(fn)` returns a **sync** wrapper (Typer needs to call it synchronously) that:

1. Calls `asyncio.run(...)` to drive an inner coroutine.
2. That inner coroutine runs your command inside `async with repository_manager_scope():` -
   see [`repository_manager_scope`](#repository_manager_scope) below.
3. On the way out (success or exception), the scope closes every repository manager session
   `load_repository_manager` opened during the command, and clears the manager cache - so the
   *next* command invocation starts clean rather than reusing a stale/closed session.

```python
from fastspine.cli.scoped_typer import command_scope

# Equivalent to what ScopedTyper does for you automatically:
wrapped = command_scope(my_async_command)
wrapped(*args, **kwargs)  # runs synchronously, internally via asyncio.run
```

### `repository_manager_scope`

`fastspine.dependencies.repository_manager.repository_manager_scope()` is the async context
manager `command_scope` uses internally. It's generic - not CLI-specific - so you can reach for it
directly in any async, non-FastAPI, non-Celery context that needs the same open-lazily/close-at-
the-end behavior (a one-off script, an async context manager of your own, etc.):

```python
from fastspine.dependencies.repository_manager import repository_manager_scope
from fastspine import load_repository_manager

async def run_once():
    async with repository_manager_scope():
        manager = load_repository_manager(PrimaryRepositoryManager)
        ...
    # session closed here, regardless of whether the block raised
```

## Sync commands aren't scoped

Only `async def` commands get wrapped. A plain sync command that calls `load_repository_manager`
directly gets a session with nobody responsible for closing it - the manager instance stays cached
in the current context until something else clears it (another `command_scope`-wrapped command
running later in the same process, or process exit). If a command needs repository managers and
you're using `ScopedTyper`, make it `async def`, even if nothing inside it strictly requires
`await` beyond the `load_*` calls.

## Sub-apps need to be `ScopedTyper` too

`ScopedTyper` only overrides `.command()` - `add_typer()` mounts whatever `Typer` subclass you give
it as-is, unchanged. That's why every command module in the example above creates its own
`ScopedTyper()` (`orders.app`, `keywords.app`) rather than a plain `typer.Typer()`: mounting a
plain `typer.Typer()` sub-app under a `ScopedTyper` top-level app does **not** retroactively wrap
its commands - each sub-app is responsible for wrapping its own.
