from fastspine.database.engine import DBConfig
from pydantic import SecretStr


def _get_url(settings: DBConfig | None, service:str = 'postgres') -> str:
    """Return the database URL from the config object."""
    if settings is None:
        raise ValueError("Config is not configured")
    if not isinstance(settings.password, SecretStr):
        raise TypeError("Password must be of type SecretStr.")
    
    return _create_db_engine(
        settings.user,
        settings.password.get_secret_value(),
        settings.host,
        str(settings.port),
        settings.dbname,
        service=service
    )

def get_postgres_url(settings: DBConfig | None) -> str:
    return _get_url(settings, service='postgresql')

def get_mysql_url(settings: DBConfig | None) -> str:
    return _get_url(settings, service='mysql')

def _create_db_engine(user, password, host, port, db_name, service: str = "postgresql") -> str:
    return (
        service + "://"
        + user
        + ":"
        + password
        + "@"
        + host
        + ":"
        + port
        + "/"
        + db_name
    )

