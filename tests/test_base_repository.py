import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from fastspine.lib.profiler import Profiler
from fastspine.mixins import SoftDeleteMixin
from fastspine.models.base import Base
from fastspine.repositories.base_repository import BaseRepository
from fastspine.schemas.pagination_model import PaginationParams


class _Widget(Base):
    """Plain (non-soft-deletable) test model."""

    __tablename__ = "test_widgets"

    name: Mapped[str] = mapped_column(nullable=False)


class _SoftWidget(Base, SoftDeleteMixin):
    """Soft-deletable test model."""

    __tablename__ = "test_soft_widgets"

    name: Mapped[str] = mapped_column(nullable=False)


class _WidgetRepository(BaseRepository[_Widget]):
    """Repository for the plain test model."""


class _SoftWidgetRepository(BaseRepository[_SoftWidget]):
    """Repository for the soft-deletable test model."""


@pytest.fixture
def sync_session():
    """A `Session` bound to a fresh in-memory SQLite database with the test tables created."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest_asyncio.fixture
async def async_session():
    """An `AsyncSession` bound to a fresh in-memory SQLite database with the test tables created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session = AsyncSession(engine)
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.fixture
def widget_repo(sync_session):
    """A `_WidgetRepository` bound to the sync in-memory database."""
    return _WidgetRepository(db=sync_session, profiler=Profiler())


@pytest.fixture
def soft_widget_repo(sync_session):
    """A `_SoftWidgetRepository` bound to the sync in-memory database."""
    return _SoftWidgetRepository(db=sync_session, profiler=Profiler())


@pytest_asyncio.fixture
async def async_widget_repo(async_session):
    """A `_WidgetRepository` bound to the async in-memory database."""
    return _WidgetRepository(db=async_session, profiler=Profiler())


@pytest_asyncio.fixture
async def async_soft_widget_repo(async_session):
    """A `_SoftWidgetRepository` bound to the async in-memory database."""
    return _SoftWidgetRepository(db=async_session, profiler=Profiler())


# --- sync CRUD -----------------------------------------------------------------------------


def test_sync_create_and_get_by_id(widget_repo):
    """A created row can be fetched back by its id."""
    widget = widget_repo.sync_create(_Widget(name="first"), flush=True)

    fetched = widget_repo.sync_get_by_id(widget.id)

    assert fetched is not None
    assert fetched.name == "first"


def test_sync_get_by_id_returns_none_for_missing_row(widget_repo):
    """A missing id gives `None`, not an exception."""
    assert widget_repo.sync_get_by_id(999) is None


def test_sync_get_instance_raises_for_missing_row(widget_repo):
    """`sync_get_instance` raises instead of silently returning `None`."""
    with pytest.raises(ValueError, match="does not exist"):
        widget_repo.sync_get_instance(999)


def test_sync_filter_by_and_count_by(widget_repo):
    """Filtering and counting agree on the same matching rows."""
    widget_repo.sync_create(_Widget(name="a"), flush=True)
    widget_repo.sync_create(_Widget(name="b"), flush=True)

    results = widget_repo.sync_filter_by(_Widget.name == "a")

    assert [w.name for w in results] == ["a"]
    assert widget_repo.sync_count_by(_Widget.name == "a") == 1
    assert widget_repo.sync_count_by() == 2


def test_sync_delete(widget_repo):
    """A deleted row is no longer retrievable."""
    widget = widget_repo.sync_create(_Widget(name="gone"), flush=True)

    widget_repo.sync_delete(widget, commit=True)

    assert widget_repo.sync_get_by_id(widget.id) is None


def test_sync_bulk_delete(widget_repo):
    """Bulk delete removes every matching row in one call."""
    ids = [widget_repo.sync_create(_Widget(name=f"w{i}"), flush=True).id for i in range(3)]

    widget_repo.sync_bulk_delete(ids, commit=True)

    assert widget_repo.sync_count_by() == 0


def test_sync_bulk_delete_rejects_soft_deletable_model(soft_widget_repo):
    """A soft-deletable model must use `sync_bulk_soft_delete` instead."""
    with pytest.raises(TypeError, match="use bulk soft delete instead"):
        soft_widget_repo.sync_bulk_delete([1, 2])


# --- soft delete -----------------------------------------------------------------------------


def test_sync_soft_delete_hides_the_row_from_default_lookups(soft_widget_repo):
    """A soft-deleted row is excluded from `sync_get_by_id`/`sync_filter_one_by`, but still exists."""
    widget = soft_widget_repo.sync_create(_SoftWidget(name="soft"), flush=True)

    soft_widget_repo.sync_soft_delete(widget, commit=True)

    assert widget.is_deleted
    assert soft_widget_repo.sync_get_by_id(widget.id) is None
    assert soft_widget_repo.sync_filter_one_by(_SoftWidget.name == "soft") is None


def test_sync_delete_on_a_soft_deletable_model_is_rejected(soft_widget_repo):
    """Regression test for the `SoftDeleteMixin` safety net: direct deletion must be blocked."""
    widget = soft_widget_repo.sync_create(_SoftWidget(name="protected"), flush=True)

    with pytest.raises(RuntimeError, match="Use soft_delete"):
        soft_widget_repo.sync_delete(widget, commit=True)


def test_sync_bulk_soft_delete(soft_widget_repo):
    """Bulk soft delete marks every matching row as deleted without removing it."""
    ids = [soft_widget_repo.sync_create(_SoftWidget(name=f"s{i}"), flush=True).id for i in range(3)]

    soft_widget_repo.sync_bulk_soft_delete(ids, commit=True)

    assert soft_widget_repo.sync_count_by() == 0  # excluded by the default not-deleted filter


# --- async CRUD -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_create_and_get_by_id(async_widget_repo):
    """The async counterpart of create + get behaves the same as the sync one."""
    widget = await async_widget_repo.create(_Widget(name="first"), flush=True)

    fetched = await async_widget_repo.get_by_id(widget.id)

    assert fetched is not None
    assert fetched.name == "first"


@pytest.mark.asyncio
async def test_async_methods_reject_a_sync_session(widget_repo):
    """Calling an async method on a sync-backed repository must raise, not silently misbehave."""
    with pytest.raises(TypeError):
        await widget_repo.get_by_id(1)
    with pytest.raises(TypeError):
        await widget_repo.create(_Widget(name="x"))
    with pytest.raises(TypeError):
        await widget_repo.delete(_Widget(name="x"))


@pytest.mark.asyncio
async def test_async_filter_by_and_count_by(async_widget_repo):
    """Async filtering and counting agree on the same matching rows."""
    await async_widget_repo.create(_Widget(name="a"), flush=True)
    await async_widget_repo.create(_Widget(name="b"), flush=True)

    results = await async_widget_repo.filter_by(_Widget.name == "a")

    assert [w.name for w in results] == ["a"]
    assert await async_widget_repo.count_by(_Widget.name == "a") == 1


@pytest.mark.asyncio
async def test_async_soft_delete_hides_the_row(async_soft_widget_repo):
    """The async soft delete path excludes the row from default lookups, same as the sync one."""
    widget = await async_soft_widget_repo.create(_SoftWidget(name="soft"), flush=True)
    widget_id = widget.id  # read before `commit()` expires the instance's attributes

    await async_soft_widget_repo.soft_delete(widget, commit=True)

    assert await async_soft_widget_repo.get_by_id(widget_id) is None


@pytest.mark.asyncio
async def test_async_bulk_delete_rejects_soft_deletable_model(async_soft_widget_repo):
    """Same guard as the sync path: bulk-deleting a soft-deletable model is rejected."""
    with pytest.raises(TypeError, match="use bulk soft delete instead"):
        await async_soft_widget_repo.bulk_delete([1, 2])


# --- raw SQL helpers (AbstractRepository) -----------------------------------------------------


def test_sync_fetch_list_runs_a_raw_select(widget_repo):
    """Regression test: `sync_fetch_list` must pass a `text()`-wrapped query to `.execute()`."""
    widget_repo.sync_create(_Widget(name="raw"), flush=True)

    rows = widget_repo.sync_fetch_list("SELECT name FROM test_widgets")

    assert rows == [{"name": "raw"}]


def test_sync_fetchone_runs_a_raw_select(widget_repo):
    """`sync_fetchone` returns the first row as a mapping."""
    widget_repo.sync_create(_Widget(name="only"), flush=True)

    row = widget_repo.sync_fetchone("SELECT name FROM test_widgets")

    assert row.name == "only"


def test_sync_fetch_paginated_runs_a_raw_select(widget_repo):
    """Regression test: `sync_fetch_paginated` must wrap both the count and page query in `text()`."""
    for i in range(3):
        widget_repo.sync_create(_Widget(name=f"p{i}"), flush=True)

    result = widget_repo.sync_fetch_paginated("SELECT name FROM test_widgets", PaginationParams(limit=2, offset=0))

    assert result.count == 3
    assert len(result.rows) == 2


def test_sync_execute_df_query_runs_a_raw_select(widget_repo):
    """Regression test: `sync_execute_df_query` must wrap the query in `text()`."""
    widget_repo.sync_create(_Widget(name="df"), flush=True)

    df = widget_repo.sync_execute_df_query("SELECT name FROM test_widgets")

    assert df["name"].tolist() == ["df"]


def test_only_select_validation_rejects_non_select_queries(widget_repo):
    """A non-SELECT statement must be rejected before it ever reaches the database."""
    with pytest.raises(ValueError, match="Only SELECT"):
        widget_repo.sync_fetch_list("DELETE FROM test_widgets")


@pytest.mark.asyncio
async def test_fetch_list_runs_a_raw_select(async_widget_repo):
    """The async `fetch_list` already wrapped its query in `text()`; confirm it still works."""
    await async_widget_repo.create(_Widget(name="raw"), flush=True)

    rows = await async_widget_repo.fetch_list("SELECT name FROM test_widgets")

    assert rows == [{"name": "raw"}]


@pytest.mark.asyncio
async def test_execute_df_query_runs_a_raw_select(async_widget_repo):
    """Regression test: the async `execute_df_query` must wrap the query in `text()`."""
    await async_widget_repo.create(_Widget(name="df"), flush=True)

    df = await async_widget_repo.execute_df_query("SELECT name FROM test_widgets")

    assert df["name"].tolist() == ["df"]
