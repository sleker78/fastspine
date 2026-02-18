from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta


def is_date_in_future(date: datetime) -> bool:
    """Check if the provided date is in the future."""
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date > datetime.now(timezone.utc)


def format_date(date: datetime, date_format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format the date to a specific string format."""
    return date.strftime(date_format) if date else ""


def now(timezone=timezone.utc) -> datetime:
    """Get the current date and time in UTC."""
    return datetime.now(timezone)


def month_diff(start_date: datetime, end_date: datetime | None = None) -> int:
    """Calculate the difference in months between start_date and end_date (or now if None)."""
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)

    if end_date is None:
        end_date = datetime.now(timezone.utc)
    elif end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    delta = relativedelta(end_date, start_date)
    return delta.years * 12 + delta.months
