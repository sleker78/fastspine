import hashlib
import importlib
import json

from celery import Task
from celery.signals import task_failure, task_postrun, task_prerun

from ..ctx.ctx_pool import ctxpool
from ..database.sessions import SessionConnectionPool
from ..redis.client import get_redis_client
from ..settings import get_core_settings
from ..util.debug_util import DebugUtil


class BaseTask(Task):
    """A base task class that can be extended for custom behavior."""

    @staticmethod
    def generate_unique_task_id(task_name: str, args=None, kwargs=None):
        """Generate a unique task ID based on method name and arguments."""
        args = args or {}
        kwargs = kwargs or {}
        settings = get_core_settings()
        # Use method name, arguments, and keyword arguments to generate a hash
        task_data = {"method": task_name, "args": args, "kwargs": kwargs}
        task_data_str = json.dumps(task_data, sort_keys=True)  # Ensure consistent order of keys
        return f"{settings.CACHE_KEY_PREFIX}{hashlib.sha256(task_data_str.encode()).hexdigest()}"

    def _cache_task_id(self, task_key):
        """Store the task ID in Redis to mark the task as already executed."""
        redis_client = get_redis_client()
        if redis_client is not None:
            return redis_client.set(task_key, "exists", nx=True)  # No expiration time set

        return None

    def apply_async(self, args=None, kwargs=None, *other_args, **other_kwargs):
        """Override apply_async to generate a unique task ID before execution."""
        DebugUtil.debug(f"Applying task {self.name} with args: {args}, kwargs: {kwargs}")
        task_key = BaseTask.generate_unique_task_id(self.name, args, kwargs)

        if not self._cache_task_id(task_key):
            DebugUtil.debug(f"Task with key {task_key} already exists. Skipping execution.")
            return {"status": f"Task with key {task_key} already exists. Skipping execution."}

        DebugUtil.debug(f"Task with key {task_key} does not exist. Proceeding with execution.")

        # Call the original apply_async method to proceed with task execution
        try:
            return super().apply_async(args, kwargs, *other_args, **other_kwargs)
        except Exception:
            redis_client = get_redis_client()
            if redis_client is not None:
                redis_client.delete(task_key)
            raise

    @staticmethod
    def _clear_cache():
        """Clear the task cache."""
        # clear_repo_cache()
        # clear_service_cache()
        ctxpool.clear()

    @task_prerun.connect
    def task_prerun_handler(task_id, task, args, kwargs, **extra_kwargs):
        """Handle task execution before running."""
        DebugUtil.debug(f"Task {task.name} started with task ID: {task_id}")
        BaseTask._clear_cache()
        SessionConnectionPool.run()

    @task_postrun.connect
    def task_postrun_handler(sender: "BaseTask | None" = None, task_id=None, args=None, kwargs=None, **other_kwargs):
        """Handle task completion after running."""
        if sender is not None:
            DebugUtil.debug(f"Task {sender.name} completed with task ID: {task_id}")
            if task_id is not None:
                task_key = BaseTask.generate_unique_task_id(sender.name, args, kwargs)
            redis_client = get_redis_client()
            if redis_client is not None:
                DebugUtil.debug(f"Deleting task key {task_key} from Redis.")
                redis_client.delete(task_key)
        DebugUtil.debug(f"{SessionConnectionPool.__name__} stopping.")
        SessionConnectionPool.stop()
        BaseTask._clear_cache()

    @task_failure.connect
    def task_failure_handler(sender: "BaseTask | None" = None, exception=None, args=None, kwargs=None, **other_kwargs):
        """Handle task failure."""
        if sender is None:
            return

        # === Fallback call ===
        try:
            failed_method_sufix = "__fallback"
            task_name = sender.run.__name__
            failed_func_name = f"{task_name}{failed_method_sufix}"
            mod = importlib.import_module(sender.__module__)
            failed_func = getattr(mod, failed_func_name, None)
            if callable(failed_func):
                failed_func(*args, **kwargs)
            else:
                DebugUtil.debug(f"Fallback method {failed_func_name} not defined")
        except Exception as e:
            DebugUtil.debug(f"Fallback handler error: {e}")
        BaseTask._clear_cache()
