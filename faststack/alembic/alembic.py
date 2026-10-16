import importlib
import time
import os
from alembic import context
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from sqlalchemy.exc import OperationalError

from ..models.base import Base

def _import_all_models(directories_dict: dict[str, str]) -> None:
    """Import all Python modules in the specified directories and their subdirectories."""
    for directory, base_package in directories_dict.items():
        for root, dirs, files in os.walk(directory):  # noqa: B007
            package_path = root.replace(directory, "").strip(os.path.sep).replace(os.path.sep, ".")
            package_name = f"{base_package}.{package_path}" if package_path else base_package

            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    module_name = file[:-3]  # Remove `.py`
                    full_module_name = f"{package_name}.{module_name}"
                    try:
                        importlib.import_module(full_module_name)
                    except ModuleNotFoundError as e:
                        print(f"Module {full_module_name} not found: {e}")
                    except Exception as e:
                        print(f"An error occurred while importing {full_module_name}: {e}")

def run_migrations_offline(db_uri: str, models_directory: str, models_folder: str|None = None) -> None:
    # Specify the directory containing your models
    models_folder = models_folder or os.path.join(os.path.dirname(__file__), "../src/models")
    models_directory_base = models_folder
    models_directories = {
        models_directory_base: models_directory,
    }

    config = context.config
    # Interpret the config file for Python logging.
    # This line sets up loggers basically.
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)

    _import_all_models(models_directories)
    # add your model's MetaData object here
    # for 'autogenerate' support
    # from myapp import mymodel
    # target_metadata = mymodel.Base.metadata
    target_metadata = Base.metadata

    url = db_uri
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online(db_uri: str) -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    config = context.config
    config.set_main_option("sqlalchemy.url", db_uri)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    target_metadata = Base.metadata
    max_retries = 10
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            with connectable.connect() as connection:
                context.configure(connection=connection, target_metadata=target_metadata)

                with context.begin_transaction():
                    context.run_migrations()
                break
        except OperationalError as e:
            if attempt < max_retries - 1:
                print(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
            else:
                print(f"Failed to connect to database after {max_retries} attempts")
                raise