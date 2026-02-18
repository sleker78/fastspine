import inspect
from typing import Any, Dict, List, Type, TypeVar

from pydantic import BaseModel

# worker scope cache, prewarm up cache
annotations_classes: Dict[Type[Any], Dict[str, Any]] = {}

T = TypeVar("T")


def get_annotations(cls: Type[T], mandatory_params: List[str] | None = None):
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


def map_to_model(data: list[dict], model: Type[BaseModel]) -> list[BaseModel]:
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
