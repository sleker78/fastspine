from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Pagination parameters."""

    limit: int = Field(default=10, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class PaginatedData[T: BaseModel](BaseModel):
    """Paginated data."""

    count: int = Field(default=0, ge=0)
    data: list[T] = Field(default_factory=list)


class PaginatedList:
    """Paginated list."""

    count: int = Field(default=0, ge=0)
    rows: list = []

    def __init__(self, count: int = 0, rows: list | None = None):
        self.count = count
        self.rows = rows if rows is not None else []
