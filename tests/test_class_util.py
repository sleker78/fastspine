from typing import List

import pytest
from pydantic import BaseModel

from fastspine.util.class_util import (
    first_parameter_type,
    function_parameters,
    get_annotations,
    get_base_type,
    map_to_model,
)


class Dummy:
    """Dummy class for testing annotations."""

    def __init__(self, a: int, b: str):
        pass


class DummyMissingAnn:
    """Dummy class with a missing annotation for testing."""

    def __init__(self, a, b: str):
        pass


class DummyMissingParam:
    """Dummy class with a missing annotation for testing."""

    def __init__(self, b: str):
        pass


class Model(BaseModel):
    """Pydantic model for testing mapping."""

    x: int
    y: str


def test_get_annotations_basic():
    """Test getting annotations from a class type."""
    anns = get_annotations(Dummy)
    assert anns == {"a": int, "b": str}


def test_get_annotations_missing_annotation():
    """Test that an error is raised when a parameter is missing an annotation."""
    with pytest.raises(ValueError):
        get_annotations(DummyMissingAnn)


def test_get_annotations_mandatory_params():
    """Test getting annotations with mandatory parameters."""
    anns = get_annotations(Dummy, mandatory_params=["a"])
    assert "a" in anns
    with pytest.raises(ValueError):
        get_annotations(DummyMissingParam, mandatory_params=["nonexistent"])


def test_get_annotations_invalid_input():
    """Test that an error is raised when the input is not a class instance."""
    with pytest.raises(ValueError):
        get_annotations(int)  # Passing a class instead of an instance


def test_first_parameter_type():
    """Test getting the type of the first parameter of a function."""

    def foo(x: int, y: str):
        pass

    assert first_parameter_type(foo) is int


def test_get_base_type_basic():
    """Test extracting the base type from an Annotated type."""
    assert get_base_type(List[int]) is list
    assert get_base_type(int) is int


def test_function_parameters():
    """Test getting function parameters."""

    def foo(a: int, b: str):
        pass

    params = function_parameters(foo)
    assert "a" in params and "b" in params
    assert params["a"].annotation is int


def test_map_to_model():
    """Test mapping a list of dictionaries to a list of model instances."""
    data = [{"x": 1, "y": "a"}, {"x": 2, "y": "b"}]
    models = map_to_model(data, Model)
    assert all(isinstance(m, Model) for m in models)
    assert models[0].x == 1 and models[0].y == "a"
