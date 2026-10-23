import pytest
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from fastspine.cli.scoped_typer import ScopedTyper, command_scope
from fastspine.dependencies.repository_manager import _repo_manager_cache_var, load_repository_manager

runner = CliRunner()


def test_command_scope_runs_the_coroutine_and_returns_its_result():
    """`command_scope` drives the wrapped coroutine to completion via `asyncio.run`."""

    async def handler(x: int) -> int:
        return x * 2

    wrapped = command_scope(handler)

    assert wrapped(21) == 42


def test_command_scope_closes_repository_manager_sessions(sync_repo_manager_class):
    """Whatever `load_repository_manager` opened during the command is closed once it returns."""

    async def handler():
        manager = load_repository_manager(sync_repo_manager_class)
        assert isinstance(manager.db, Session)

    command_scope(handler)()

    assert _repo_manager_cache_var.get() is None


def test_command_scope_closes_sessions_even_if_the_command_raises(sync_repo_manager_class):
    """The scope's cleanup must run on the exception path too, not just on success."""

    async def handler():
        load_repository_manager(sync_repo_manager_class)
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        command_scope(handler)()

    assert _repo_manager_cache_var.get() is None


def test_scoped_typer_wraps_async_commands_with_command_scope(sync_repo_manager_class):
    """An async command registered on `ScopedTyper` gets its sessions closed after it runs."""
    app = ScopedTyper()

    @app.command()
    async def sync_db():  # noqa: F811 - typer command, name doesn't matter
        manager = load_repository_manager(sync_repo_manager_class)
        print(manager.db is not None)

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    assert _repo_manager_cache_var.get() is None


def test_scoped_typer_leaves_sync_commands_unwrapped(sync_repo_manager_class):
    """A sync command isn't wrapped with `command_scope`, so its sessions aren't auto-closed."""
    app = ScopedTyper()

    @app.command()
    def sync_db():
        load_repository_manager(sync_repo_manager_class)

    result = runner.invoke(app, [])

    assert result.exit_code == 0
    # Not wrapped, so nothing closed the manager it loaded - it's still sitting in the cache.
    assert _repo_manager_cache_var.get() is not None
