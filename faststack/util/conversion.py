import math
from typing import Iterable, TypeVar

T = TypeVar("T")


def convert_nan_to_none(v):
    """If the value is NaN, convert it to None."""
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def to_list(value: Iterable[T] | None) -> list[T]:
    """Convert an iterable to a list, or return an empty list if None.

    Args:
        value: The iterable to convert.

    Returns:
        A list containing the elements of the iterable, or an empty list if the input is None.
    """
    if value is None:
        return []
    return list(value)


def to_set(value: Iterable[T] | None) -> set[T]:
    """Convert an iterable to a set, or return an empty set if None.

    Args:
        value: The iterable to convert.

    Returns:
        A set containing the elements of the iterable, or an empty set if the input is None.
    """
    if value is None:
        return set()
    return set(value)
