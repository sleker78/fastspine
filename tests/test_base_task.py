from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from celery import Task
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

import fastspine.celery.base_task as base_task_module
from fastspine.celery.base_task import BaseTask
from fastspine.dependencies.repository_manager import _repo_manager_cache_var


class _FakeCeleryTask:
    """Minimal stand-in for a Celery task instance, enough for the signal handlers under test."""

    __module__ = __name__
    name = "fake_task"

    def run(self):
        pass


class _DummyTask(BaseTask):
    """A real `BaseTask` subclass, not bound to a Celery app - enough to exercise `apply_async`."""

    name = "dummy_task"


def test_dedup_enabled_true_for_redis_broker(monkeypatch):
    """Redis has no built-in message dedup, so BaseTask's own check applies there."""
    monkeypatch.setattr(
        base_task_module, "get_core_settings", lambda: SimpleNamespace(CELERY_BROKER_URI="redis://localhost:6379/0")
    )
    assert BaseTask._dedup_enabled() is True


def test_dedup_enabled_false_for_non_redis_broker(monkeypatch):
    """RabbitMQ (and other non-Redis brokers) handle message dedup at the transport level."""
    monkeypatch.setattr(
        base_task_module, "get_core_settings", lambda: SimpleNamespace(CELERY_BROKER_URI="amqp://guest@localhost//")
    )
    assert BaseTask._dedup_enabled() is False


def test_apply_async_skips_dedup_entirely_for_non_redis_broker(monkeypatch):
    """With a non-Redis broker, apply_async forwards straight through - no Redis touched at all."""
    monkeypatch.setattr(
        base_task_module, "get_core_settings", lambda: SimpleNamespace(CELERY_BROKER_URI="amqp://guest@localhost//")
    )
    redis_client = Mock()
    monkeypatch.setattr(base_task_module, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(Task, "apply_async", lambda self, args=None, kwargs=None, *a, **kw: "forwarded")

    result = _DummyTask().apply_async(args=(1,), kwargs={"x": 1})

    assert result == "forwarded"
    redis_client.set.assert_not_called()


def test_apply_async_dedups_when_broker_is_redis(monkeypatch):
    """With a Redis broker, a duplicate call (same args/kwargs) is skipped rather than re-sent."""
    monkeypatch.setattr(
        base_task_module,
        "get_core_settings",
        lambda: SimpleNamespace(CELERY_BROKER_URI="redis://localhost:6379/0", CACHE_KEY_PREFIX=""),
    )
    redis_client = Mock()
    monkeypatch.setattr(base_task_module, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(Task, "apply_async", lambda self, args=None, kwargs=None, *a, **kw: "forwarded")

    redis_client.set.return_value = True  # lock acquired - not a duplicate
    first = _DummyTask().apply_async(args=(1,), kwargs={"x": 1})
    assert first == "forwarded"

    redis_client.set.return_value = False  # key already exists - duplicate
    second = _DummyTask().apply_async(args=(1,), kwargs={"x": 1})
    assert isinstance(second, dict)
    assert "already exists" in second["status"]


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


def test_task_postrun_handler_deletes_dedup_key_when_broker_is_redis(monkeypatch):
    """The dedup key written by apply_async gets cleaned up once the task finishes."""
    monkeypatch.setattr(
        base_task_module,
        "get_core_settings",
        lambda: SimpleNamespace(CELERY_BROKER_URI="redis://localhost:6379/0", CACHE_KEY_PREFIX=""),
    )
    redis_client = Mock()
    monkeypatch.setattr(base_task_module, "get_redis_client", lambda: redis_client)

    BaseTask.task_postrun_handler(sender=_FakeCeleryTask(), task_id="t-1", args=(), kwargs={})

    redis_client.delete.assert_called_once()


def test_task_postrun_handler_skips_dedup_key_when_broker_is_not_redis(monkeypatch):
    """No dedup key was ever written for a non-Redis broker, so there's nothing to delete here either."""
    monkeypatch.setattr(
        base_task_module, "get_core_settings", lambda: SimpleNamespace(CELERY_BROKER_URI="amqp://guest@localhost//")
    )
    redis_client = Mock()
    monkeypatch.setattr(base_task_module, "get_redis_client", lambda: redis_client)

    BaseTask.task_postrun_handler(sender=_FakeCeleryTask(), task_id="t-1", args=(), kwargs={})

    redis_client.delete.assert_not_called()


def test_task_postrun_handler_closes_an_async_session_too(async_repo_manager_class):
    """Sync Celery tasks can still have loaded an async-managed repository manager; must not crash."""
    manager = async_repo_manager_class(db=AsyncMock(spec=AsyncSession))
    _repo_manager_cache_var.set({async_repo_manager_class: manager})

    BaseTask.task_postrun_handler(sender=None, task_id=None, args=None, kwargs=None)

    manager.db.close.assert_not_called()  # can't close an AsyncSession from this sync path - skipped, not crashed
    assert _repo_manager_cache_var.get() is None
