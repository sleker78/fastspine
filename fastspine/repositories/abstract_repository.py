import re
from abc import ABC
from typing import Any

import pandas as pd
import polars as pl
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.expression import Selectable

from ..lib.profiler import Profiler
from ..schemas.pagination_model import PaginatedData, PaginatedList, PaginationParams
from ..types import DBSessions
from ..util.dataframe_util import map_data_to_model


class AbstractRepository(ABC):  # noqa: B024
    """Base repository class for external database operations.

    This class provides a common interface for all repository classes for externale db.
    """

    def __init__(self, db: DBSessions, profiler: Profiler):
        self.db = db
        self.profiler = profiler

    def _get_limit_offset(self, pagination: PaginationParams) -> str:
        """Returns the LIMIT and OFFSET clause for a SQL query."""
        return f" LIMIT {pagination.limit} OFFSET {pagination.offset}"

    def _only_select_validation(self, query: str | TextClause | Selectable) -> None:
        """Validates that the query is a SELECT query."""
        if isinstance(query, str):
            cleaned_query = query.strip().lower()
            contains_with = re.match(r"^\s*with\b", cleaned_query)

            starts_with_select = re.match(r"^\(*\s*select\b", cleaned_query)
            contains_union = " union " in cleaned_query
            if not (starts_with_select or contains_union or contains_with):
                raise ValueError("Only SELECT or UNION or WITH queries are allowed for fetching data.")

    def sync_fetch_paginated(
        self,
        query: str,
        pagination: PaginationParams,
        params: dict[str, Any] | None = None,
    ) -> PaginatedList:
        """Executes a native SQL query and returns the result as PaginatedList."""
        self._only_select_validation(query)
        if params is None:
            params = {}

        count_query = f"SELECT COUNT(*) FROM ({query}) AS subquery"
        count_result = self.db.execute(text(count_query), params)
        total_count = count_result.scalar()  # Get the total count of records
        query += self._get_limit_offset(pagination)
        params["limit"] = pagination.limit
        params["offset"] = pagination.offset

        results = self.db.execute(text(query), params).mappings().all()
        results = [dict(row) for row in results]

        return PaginatedList(count=total_count, rows=results)

    async def fetch_paginated(
        self,
        query: str,
        pagination: PaginationParams,
        params: dict[str, Any] | None = None,
    ) -> PaginatedList:
        """Executes a native SQL query and returns the result as PaginatedList (async version)."""
        self._only_select_validation(query)
        if params is None:
            params = {}

        count_query = f"SELECT COUNT(*) FROM ({query}) AS subquery"
        count_result = await self.db.execute(text(count_query), params)
        total_count = count_result.scalar()  # Get the total count of records
        query += self._get_limit_offset(pagination)
        params["limit"] = pagination.limit
        params["offset"] = pagination.offset

        results = await self.db.execute(text(query), params)
        results = results.mappings().all()
        results = [dict(row) for row in results]

        return PaginatedList(count=total_count, rows=results)

    def sync_fetch_dataframe(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        pagination: PaginationParams | None = None,
        model: type[BaseModel] | None = None,
        response_model: type[PaginatedData] | None = None,
    ) -> PaginatedData:
        """Executes a native SQL query and returns the result as PaginatedList."""
        self._only_select_validation(query)
        if params is None:
            params = {}
        if pagination is None:
            raise ValueError("Pagination parameters must be provided.")
        if model is None or response_model is None:
            raise ValueError("Model and response_model must be provided to map the data to the model.")

        count_query = f"SELECT COUNT(*) FROM ({query}) AS subquery"
        count_result = self.db.execute(text(count_query), params)
        total_count = count_result.scalar()  # Get the total count of records
        query += self._get_limit_offset(pagination)
        params["limit"] = pagination.limit
        params["offset"] = pagination.offset

        result = self.db.execute(text(query), params)
        data = pd.DataFrame(result.fetchall(), columns=result.keys())
        data = map_data_to_model(data, model)

        return response_model(data=data, count=total_count)

    async def fetch_dataframe(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        pagination: PaginationParams | None = None,
        model: type[BaseModel] | None = None,
        response_model: type[PaginatedData] | None = None,
    ) -> PaginatedData:
        """Executes a native SQL query and returns the result as PaginatedList (async version)."""
        self._only_select_validation(query)
        if params is None:
            params = {}
        if pagination is None:
            raise ValueError("Pagination parameters must be provided.")
        if model is None or response_model is None:
            raise ValueError("Model and response_model must be provided to map the data to the model.")

        count_query = f"SELECT COUNT(*) FROM ({query}) AS subquery"
        count_result = await self.db.execute(text(count_query), params)
        total_count = count_result.scalar()  # Get the total count of records
        query += self._get_limit_offset(pagination)
        params["limit"] = pagination.limit
        params["offset"] = pagination.offset

        result = await self.db.execute(text(query), params)
        data = pd.DataFrame(result.fetchall(), columns=result.keys())
        data = map_data_to_model(data, model)

        return response_model(data=data, count=total_count)

    def sync_fetch_list(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Executes a native SQL query and returns the result as a list of models or dicts."""
        self._only_select_validation(query)
        if params is None:
            params = {}
        results = self.db.execute(text(query), params).mappings().all()
        return [dict(row) for row in results]

    async def fetch_list(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Executes a native SQL query and returns the result as a list of models or dicts."""
        self._only_select_validation(query)
        if params is None:
            params = {}
        result = await self.db.execute(text(query), params)
        results = result.mappings().all()
        return [dict(row) for row in results]

    def sync_fetchone(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        model: type[BaseModel] | None = None,
        dataframe: bool = False,
    ) -> Any:
        """Executes a native SQL query and returns the first row of the result."""
        self._only_select_validation(query)
        query = text(query)
        if params is None:
            params = {}
        res = self.db.execute(query, params).fetchone()
        if dataframe:
            return pd.DataFrame([dict(res)], columns=res.keys())

        if model is not None and res is not None:
            return model(**dict(res))

        return res

    async def fetchone(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        model: type[BaseModel] | None = None,
    ) -> Any:
        """Executes a native SQL query and returns the first row of the result."""
        self._only_select_validation(query)
        query_stmt = text(query)
        if params is None:
            params = {}

        result = await self.db.execute(query_stmt, params)
        res = result.mappings().fetchone()

        if model is not None and res is not None:
            return model(**dict(res))

        return res

    def sync_execute_df_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        return_type: type[pd.DataFrame | pl.DataFrame] = pd,
    ) -> pd.DataFrame | pl.DataFrame:
        """Executes a native SQL query and returns the result as a pandas or polars DataFrame."""
        self._only_select_validation(query)
        if params is None:
            params = {}
        result = self.db.execute(text(query), params)
        data = result.fetchall()
        columns = result.keys()

        if return_type is pl:
            return pl.DataFrame([dict(row._mapping) for row in data])

        return pd.DataFrame(data, columns=columns)

    async def execute_df_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        return_type: type[pd.DataFrame | pl.DataFrame] = pd,
    ) -> pd.DataFrame | pl.DataFrame:
        """Executes a native SQL query and returns the result as a pandas or polars DataFrame (async version)."""
        self._only_select_validation(query)
        if params is None:
            params = {}
        result = await self.db.execute(text(query), params)
        data = result.fetchall()
        columns = result.keys()

        if return_type is pl:
            return pl.DataFrame([dict(row._mapping) for row in data])

        return pd.DataFrame(data, columns=columns)

    def _placeholders_and_params(self, values: list, prefix: str, params: dict) -> tuple[list[str], dict]:
        placeholders = []
        for idx, value in enumerate(values):
            key = f"{prefix}_{idx}"
            placeholders.append(f":{key}")
            params[key] = value
        return placeholders, params

    def _create_filter_condition(self, filters: list[str], global_filters: list[str]) -> str:
        """Creates a filter condition string based on the provided filters and global filters."""
        clauses = []
        where_clause = ""
        if filters:
            clauses.append("(" + " AND ".join(filters) + ")")

        if global_filters:
            clauses.append("(" + " AND ".join(global_filters) + ")")

        if clauses:
            where_clause = " WHERE " + " OR ".join(clauses)

        return where_clause
