# Full example: one database, one model, Redis caching, no Celery

Everything else in `_docs/` covers one piece at a time. This doc wires the simplest possible app
end to end - one database, one model, one repository, one service, Redis caching on a read method
- so you can see how the pieces from [Configuration](configuration.md), [Database](database.md)
and [Caching](caching.md) actually fit together in a single running app. No Celery here; see
[Celery](celery.md) separately if/when you need background tasks.

```
myapp/
  settings.py
  db/
    sessions.py       # RepositoryManager classes
  bootstrap.py         # register_sessions(...)
  models/
    order.py
  repositories/
    order_repository.py
  services/
    order_service.py
  main.py
```

## 1. Settings

One `DBConfig` for the one database, plus caching - both come from the same settings object (see
[Configuration](configuration.md) for the full field list):

```python
# myapp/settings.py
from pydantic_settings import BaseSettings

from fastspine.database.engine import DBConfig, DBServices


class AppSettings(BaseSettings):
    PROJECT_NAME: str = "My App"

    DB_NAME: str = "app"
    DB_USER: str = "app_user"
    DB_PASSWORD: str = ""
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432

    CACHE_ENABLED: bool = True
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    @property
    def db_config(self) -> DBConfig:
        return DBConfig(
            dbname=self.DB_NAME,
            user=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            service=DBServices.ASYNC_POSTGRES,
        )


settings = AppSettings()
```

Start a local Redis the same way described in [Caching](caching.md#running-redis-locally):
`docker run -d --name redis -p 6379:6379 redis:7-alpine`. Nothing else is needed on the caching
side - no schema, no separate install.

## 2. The model

One table, mapped against FastSpine's declarative `Base` so `BaseRepository` can work with it:

```python
# myapp/models/order.py
from sqlalchemy.orm import Mapped, mapped_column

from fastspine.models.base import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str]
    total_cents: Mapped[int]
```

## 3. The `RepositoryManager` and its registration

One database means one `RepositoryManager` subclass. Per [Database](database.md), it goes in its
own file even though there's only one of it - that stays the obvious place to add a second one
later:

```python
# myapp/db/sessions.py
from sqlalchemy.ext.asyncio import AsyncSession

from fastspine import RepositoryManager


class AppRepositoryManager(RepositoryManager[AsyncSession]):
    """Repository manager for the app's one database."""
```

Registration is a separate, small module, imported explicitly and first by anything that uses it
(see [Database: registration](database.md#3-registration-register_sessions-in-its-own-module) for
why this has to be explicit per-process):

```python
# myapp/bootstrap.py
from fastspine.dependencies.database import register_sessions

from myapp.db.sessions import AppRepositoryManager
from myapp.settings import settings

register_sessions([
    (AppRepositoryManager, settings.db_config),
])
```

## 4. The repository

```python
# myapp/repositories/order_repository.py
from fastspine import BaseRepository

from myapp.models.order import Order


class OrderRepository(BaseRepository[Order]):
    """Repository for `Order` rows."""
    # inherits get_by_id, filter_by, create, ... (async, since AppRepositoryManager uses AsyncSession)
```

## 5. The service - with one cached method

The service depends on `AppRepositoryManager` (constructor-injected, per
[Database: using it](database.md#4-using-it-repositories-and-services)), and caches its one
read method with `cache_method_async` (per [Caching](caching.md#decorators)):

```python
# myapp/services/order_service.py
from datetime import timedelta

from fastspine import BaseService, cache_method_async

from myapp.db.sessions import AppRepositoryManager
from myapp.models.order import Order
from myapp.repositories.order_repository import OrderRepository


class OrderService(BaseService):
    def __init__(self, db: AppRepositoryManager):
        self.db = db

    async def create_order(self, customer_name: str, total_cents: int) -> int:
        order = Order(customer_name=customer_name, total_cents=total_cents)
        order = await self.db.get(OrderRepository).create(order, commit=True)
        return order.id

    @cache_method_async(expire=timedelta(minutes=5))
    async def get_order(self, order_id: int) -> dict:
        order = await self.db.get(OrderRepository).get_by_id(order_id)
        return {"id": order.id, "customer_name": order.customer_name, "total_cents": order.total_cents}
```

`get_order` is cached per `order_id` for 5 minutes (`cache_method_async` keys on the method's
arguments, excluding `self` - see [Caching: decorators](caching.md#decorators)); `create_order` is
never cached, and doesn't need to be - it writes, it doesn't read.

## 6. Wiring it up

```python
# myapp/main.py
import myapp.bootstrap  # noqa: F401  (must run before any route uses OrderService)

from typing import Annotated

from fastapi import Depends

from fastspine import FastSpineApp, service_dep

from myapp.settings import settings
from myapp.services.order_service import OrderService

app = FastSpineApp(settings=settings, title=settings.PROJECT_NAME)

OrderServiceDep = Annotated[OrderService, Depends(service_dep(OrderService))]


@app.post("/orders")
async def create_order(customer_name: str, total_cents: int, service: OrderServiceDep):
    order_id = await service.create_order(customer_name, total_cents)
    return {"id": order_id}


@app.get("/orders/{order_id}")
async def get_order(order_id: int, service: OrderServiceDep):
    return await service.get_order(order_id)
```

## 7. Running it

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine   # caching
uvicorn myapp.main:app --reload
```

That's the whole app: `POST /orders` writes a row and returns its id; `GET /orders/{id}` reads it
through the cache - the first call per `order_id` hits the database, every call for the next 5
minutes (per process) is served from Redis without touching the database at all.

Everything here composes the same way with more of each piece - a second `RepositoryManager` for
a second database, more repositories per manager, more cached/uncached methods per service, a CLI
or Celery entrypoint reusing the same `bootstrap.py` - see [Database](database.md),
[Caching](caching.md), [CLI](cli.md), and [Celery](celery.md) for each of those, respectively.
