from dataclasses import fields
from enum import Enum
from typing import Self

from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine

from ..types import DBEngines


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
    autocommit: bool = Field(default=False)

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
            return f"{driver}://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.dbname}"

        raise TypeError(f"Password must be of type SecretStr.{self.password} is of type {type(self.password)}")

    def db_url(self) -> str:
        """Generate the connection URL based on the configuration."""
        if isinstance(self.password, SecretStr):
            return f"{self.service.value}://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.dbname}"

        raise TypeError(f"Password must be of type SecretStr333.{self.password} is of type {type(self.password)}")

    @classmethod
    def get_db_config(cls, config: dict | Self) -> Self:
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

    def create_engine(self) -> Engine:
        """Create and return the database engine."""
        if self.async_mode:
            raise ValueError("Cannot create a synchronous engine in async mode.")
        from sqlalchemy import create_engine

        return create_engine(self.connection_url(), pool_pre_ping=True)

    def create_async_engine(self) -> AsyncEngine:
        """Create and return the async database engine."""
        if not self.async_mode:
            raise ValueError("Cannot create an async engine in synchronous mode.")
        from sqlalchemy.ext.asyncio import create_async_engine

        if self.autocommit:
            return create_async_engine(
                self.connection_url(),
                pool_pre_ping=True,
                isolation_level="AUTOCOMMIT",
                pool_reset_on_return=None,
            )
        return create_async_engine(self.connection_url(), pool_pre_ping=True)

    @staticmethod
    def init_engine(config: "dict | DBConfig") -> DBEngines:
        """Initialize the database engine based on the provided configuration."""
        db_config = DBConfig.get_db_config(config)
        if db_config.async_mode:
            return db_config.create_async_engine()
        return db_config.create_engine()


class DBReadonlyConfig(DBConfig):
    """Database configuration dataclass for readonly connections."""

    autocommit: bool = Field(default=True)
