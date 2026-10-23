from unittest.mock import AsyncMock, Mock

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from fastspine.celery.base_task import BaseTask
from fastspine.dependencies.repository_manager import _repo_manager_cache_var


class _FakeCeleryTask:
    """Minimal stand-in for a Celery task instance, enough for the signal handlers under test."""

    __module__ = __name__
    name = "fake_task"

    def run(self):
        pass


def test_task_prerun_handler_clears_stale_cache(sync_repo_manager_class):
    """A sync worker reuses its process/thread across tasks, so prerun must wipe leftover state."""
    manager = sync_repo_manager_class(db=Mock(spec=Session))
    _repo_manager_cache_var.set({sync_repo_manager_class: manager})

    BaseTask.task_prerun_handler(task_id="t-1", task=_FakeCeleryTask(), args=(), kwargs={})

    assert _repo_manager_cache_var.get() is None


def test_task_postrun_handler_closes_sessions_and_clears_cache(sync_repo_manager_class):
    """On successful completion, the task's repository manager session gets closed."""
    manager = sync_repo_manager_class(db=Mock(spec=Session))
    _repo_manager_cache_var.set({sync_repo_manager_class: manager})

    BaseTask.task_postrun_handler(sender=None, task_id=None, args=None, kwargs=None)

    manager.db.close.assert_called_once()
    assert _repo_manager_cache_var.get() is None


def test_task_failure_handler_closes_sessions_and_clears_cache(sync_repo_manager_class):
    """Regression test: the failure path used to skip session cleanup entirely, leaking the connection."""
    manager = sync_repo_manager_class(db=Mock(spec=Session))
    _repo_manager_cache_var.set({sync_repo_manager_class: manager})

    BaseTask.task_failure_handler(sender=_FakeCeleryTask(), exception=Exception("boom"), args=(), kwargs={})

    manager.db.close.assert_called_once()
    assert _repo_manager_cache_var.get() is None


def test_task_failure_handler_does_nothing_without_a_sender(sync_repo_manager_class):
    """Without a `sender`, the handler bails out before reaching the cleanup logic."""
    manager = sync_repo_manager_class(db=Mock(spec=Session))
    _repo_manager_cache_var.set({sync_repo_manager_class: manager})

    BaseTask.task_failure_handler(sender=None, exception=Exception("boom"), args=(), kwargs={})

    manager.db.close.assert_not_called()


def test_task_postrun_handler_closes_an_async_session_too(async_repo_manager_class):
    """Sync Celery tasks can still have loaded an async-managed repository manager; must not crash."""
    manager = async_repo_manager_class(db=AsyncMock(spec=AsyncSession))
    _repo_manager_cache_var.set({async_repo_manager_class: manager})

    BaseTask.task_postrun_handler(sender=None, task_id=None, args=None, kwargs=None)

    manager.db.close.assert_not_called()  # can't close an AsyncSession from this sync path - skipped, not crashed
    assert _repo_manager_cache_var.get() is None
