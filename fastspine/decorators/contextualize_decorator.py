import uuid
from functools import wraps

from fastspine.lib.contextualize import contextualize

from ..util.class_util import function_parameters


def with_contextualize(**context_params):
    """Decorator to wrap Celery tasks with contextualize context.

    Args:
        **context_params: Mapping of context key to parameter name
                         e.g., input_list_id='input_list_id', task_id='request_id'

    Example:
        @client.task(bind=True, model=BaseTask, acks_late=True, reject_on_worker_lost=True)
        @with_contextualize(input_list_id='input_list_id')
        def cfp_list(self, input_list_id: int, ...):
            # Function body without the contextualize wrapper

        @client.task(bind=True, model=BaseTask, acks_late=True, reject_on_worker_lost=True)
        @with_contextualize(task_id='request_id')
        def new_request_notify(self, request_id: int, ...):
            # Function body without the contextualize wrapper
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            correlation_id = str(uuid.uuid4())
            task_name = self.name.split(".")[-1] if hasattr(self, "name") else func.__name__

            context_kwargs = {"correlation_id": correlation_id, "task_name": task_name}

            # Extract specified parameters
            if context_params:
                params = function_parameters(func)
                param_names = list(params.keys())[1:]  # Skip 'self'

                for context_key, param_name in context_params.items():
                    if param_name in param_names:
                        param_index = param_names.index(param_name)
                        if param_index < len(args):
                            context_kwargs[context_key] = args[param_index]
                        elif param_name in kwargs:
                            context_kwargs[context_key] = kwargs[param_name]

            with contextualize(**context_kwargs):
                return func(self, *args, **kwargs)

        return wrapper

    return decorator
