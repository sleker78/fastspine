import functools
import time

from sqlalchemy.exc import OperationalError


def upsert_decorator(batch_size=100, max_attempts=5, sort_key=None):
    """Decorator for batch upsert operations with retry logic.

    Args:
        batch_size (int): Number of records to process in each batch
        max_attempts (int): Maximum number of retry attempts for deadlock handling
        sort_key (callable): Optional function to sort data before batching
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(session, data, *args, **kwargs):
            # Allow overriding decorator defaults with kwargs
            actual_batch_size = kwargs.pop("batch_size", batch_size)
            actual_max_attempts = kwargs.pop("max_attempts", max_attempts)
            actual_sort_key = kwargs.pop("sort_key", sort_key)

            if len(data) == 0:
                return

            # Sort data if sort_key is provided
            if actual_sort_key:
                data = sorted(data, key=actual_sort_key)

            # Process data in batches
            for i in range(0, len(data), actual_batch_size):
                batch = data[i : i + actual_batch_size]

                # Create the upsert statement using the decorated function
                stmt = func(session, batch, *args, **kwargs)

                # Execute with retry logic
                for attempt in range(actual_max_attempts):
                    try:
                        session.execute(stmt)
                        session.commit()
                        break
                    except OperationalError as e:
                        if "deadlock detected" in str(e) and attempt < actual_max_attempts - 1:
                            session.rollback()
                            time.sleep(0.1 * (2**attempt))  # Exponential backoff
                            continue
                        raise

        return wrapper

    return decorator


def class_upsert_decorator(batch_size=100, max_attempts=5, sort_key=None, session_property="db"):
    """Decorator for batch upsert operations with retry logic.

    Args:
        batch_size (int): Number of records to process in each batch
        max_attempts (int): Maximum number of retry attempts for deadlock handling
        sort_key (callable): Optional function to sort data before batching
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, data, *args, **kwargs):
            # Allow overriding decorator defaults with kwargs
            actual_batch_size = kwargs.pop("batch_size", batch_size)
            actual_max_attempts = kwargs.pop("max_attempts", max_attempts)
            actual_sort_key = kwargs.pop("sort_key", sort_key)
            repo_manager = getattr(self, session_property)
            if hasattr(repo_manager, "db"):
                session = repo_manager.db
            else:
                raise AttributeError(f"The repository manager does not have a '{session_property}' attribute.")

            if len(data) == 0:
                return

            # Sort data if sort_key is provided
            if actual_sort_key:
                data = sorted(data, key=actual_sort_key)

            # Process data in batches
            for i in range(0, len(data), actual_batch_size):
                batch = data[i : i + actual_batch_size]

                # Create the upsert statement using the decorated function
                stmt = func(self, batch, *args, **kwargs)

                # Execute with retry logic
                for attempt in range(actual_max_attempts):
                    try:
                        session.execute(stmt)
                        session.commit()
                        break
                    except OperationalError as e:
                        if "deadlock detected" in str(e) and attempt < actual_max_attempts - 1:
                            session.rollback()
                            time.sleep(0.1 * (2**attempt))  # Exponential backoff
                            continue
                        raise

        return wrapper

    return decorator
