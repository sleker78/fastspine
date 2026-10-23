import inspect
from enum import Enum
from typing import Any, get_type_hints

import polars as pl
from pydantic import BaseModel

# worker scope cache, prewarm up cache
annotations_classes: dict[type[Any], dict[str, Any]] = {}

annotations_cache: dict[type[Any], dict[str, Any]] = {}


def get_class_annotations[T](service_class: type[T]):
    """Get the annotations of a class."""
    if service_class in annotations_cache:
        return annotations_cache[service_class]

    sig = inspect.signature(service_class.__init__)
    hints = get_type_hints(service_class.__init__)

    annotations = {}
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue
        if param_name not in hints:
            raise ValueError(
                f"Parameter '{param_name}' of {service_class.__name__} with type {param} is missing a type annotation"
            )
        annotations[param_name] = hints.get(param_name)

    annotations_cache[service_class] = annotations

    return annotations


def get_annotations[T](cls: type[T], mandatory_params: list[str] | None = None):
    """Get annotations of a class instance."""
    if cls in annotations_classes:
        return annotations_classes[cls]

    init_signature = inspect.signature(cls.__init__)
    annotations = {}

    for name, param in init_signature.parameters.items():
        if name == "self":
            continue
        if param.annotation == inspect.Parameter.empty:
            raise ValueError(f"Parameter {name} of {type(cls)} is missing a type annotation")
        if param.default is not inspect.Parameter.empty:
            pass
        annotations[name] = param.annotation

    if mandatory_params is not None:
        missing_params = [param for param in mandatory_params if param not in annotations]
        if missing_params:
            raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")

    annotations_classes[cls] = annotations
    return annotations


def first_parameter_type(func):
    """Get the type of the first parameter of the function."""
    signature = inspect.signature(func)
    first_param = next(iter(signature.parameters.values()))  # Get the first parameter
    return first_param.annotation


def get_base_type(annotated_type):
    """Extract the base type from an Annotated type."""
    if hasattr(annotated_type, "__origin__"):
        return annotated_type.__origin__
    return annotated_type


def function_parameters(func):
    """Get function parameters."""
    signature = inspect.signature(func)
    return signature.parameters


def map_to_model(data: list[dict], model: type[BaseModel]) -> list[BaseModel]:
    """Map a list of dictionaries to a list of model instances."""
    return [model(**item) for item in data]


def required_property(cls, name: str, default=None):
    """Create a required property for a class."""
    if not hasattr(cls, "__annotations__"):
        cls.__annotations__ = {}
    cls.__annotations__[name] = default
    return property(
        lambda self: getattr(self, f"_{name}", default), lambda self, value: setattr(self, f"_{name}", value)
    )


def map_data_to_model(df: pl.DataFrame, model: type[BaseModel]) -> list[BaseModel]:
    """Converts a Polars DataFrame to a list of Pydantic models.

    Null values are handled automatically during conversion.
    """
    df_clean = df.fill_nan(None)

    return [model(**row) for row in df_clean.to_dicts()]


def enum_to_json_list(enum_class: type[Enum]) -> list[dict[str, str]]:
    """Convert enum class to JSON list format for frontend."""
    return [{"id": item.name, "value": item.value} for item in enum_class]
