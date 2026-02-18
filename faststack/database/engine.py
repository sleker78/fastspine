from dataclasses import fields
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.engine import Engine


class DBServices(str, Enum):
    """Enum for database services."""

    POSTGRES = "postgres"
    MYSQL = "mysql"
    ASYNC_POSTGRES = "async_postgres"
    ASYNC_MYSQL = "async_mysql"


class DBConfig(BaseModel):
    """Database configuration dataclass."""

    dbname: str = Field()
    user: str = Field()
    host: str = Field()
    password: SecretStr | None = Field(default=None, repr=False)
    service: DBServices = Field(default=DBServices.POSTGRES)
    port: int = Field(strict=False, gt=0, le=65535)
    async_mode: bool = Field(default=False)

    def model_post_init(self, __context):
        """Validate the DBConfig fields."""
        if not (0 < self.port <= 65535):
            raise ValueError(f"Port {self.port} is out of range. Must be between 1 and 65535.")
        self._set_async()

    def _set_async(self):
        """Set async_mode based on the service."""
        if self.service in {DBServices.ASYNC_POSTGRES, DBServices.ASYNC_MYSQL}:
            self.async_mode = True
        else:
            self.async_mode = False

    def set_service(self, service: str):
        """Set the database service."""
        try:
            self.service = DBServices(service)
            self._set_async()
        except ValueError as err:
            raise ValueError(f"Unsupported database service: {service}") from err

    def connection_url(self) -> str:
        """Generate the connection URL based on the configuration."""
        driver_map = {
            DBServices.POSTGRES: "postgresql+psycopg2",
            DBServices.ASYNC_POSTGRES: "postgresql+asyncpg",
            DBServices.MYSQL: "mysql+pymysql",
            DBServices.ASYNC_MYSQL: "mysql+aiomysql",
        }
        driver = driver_map[self.service]
        if isinstance(self.password, SecretStr):
            self.password = self.password.get_secret_value()
        else:
            raise TypeError("Password must be of type SecretStr.")
        return f"{driver}://{self.user}:{self.password}@{self.host}:{self.port}/{self.dbname}"

    @classmethod
    def get_db_config(cls, config: Any) -> Self:
        """Get the database configuration from the provided config."""
        if isinstance(config, cls):
            return config

        required_fields = [f.name for f in fields(cls) if f.name != "async_mode"]

        if isinstance(config, dict):
            for f_name in required_fields:
                if f_name not in config:
                    raise TypeError(f"Missing required field '{f_name}' in config dict.")
            return cls(**{f_name: config[f_name] for f_name in required_fields})

        for f_name in required_fields:
            if not hasattr(config, f_name):
                raise TypeError(f"Missing required field '{f_name}' in config object.")

        return cls(**{f_name: getattr(config, f_name) for f_name in required_fields})

    def create_engine(self) -> Any:
        """Create and return the database engine."""
        if self.async_mode:
            raise ValueError("Cannot create a synchronous engine in async mode.")
        from sqlalchemy import create_engine

        return create_engine(self.connection_url(), pool_pre_ping=True)

    def create_async_engine(self) -> Any:
        """Create and return the async database engine."""
        if not self.async_mode:
            raise ValueError("Cannot create an async engine in synchronous mode.")
        from sqlalchemy.ext.asyncio import create_async_engine

        return create_async_engine(self.connection_url())

    @staticmethod
    def init_engine(config: Any) -> Engine:
        """Initialize the database engine based on the provided configuration."""
        db_config = DBConfig.get_db_config(config)
        if db_config.async_mode:
            return db_config.create_async_engine()
        return db_config.create_engine()
