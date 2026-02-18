import json
import pickle
from typing import Any, Protocol

from pydantic import BaseModel


class Encoder(Protocol):
    """Abstract base class for encoding and decoding cache responses."""

    @staticmethod
    def encode(value: Any) -> Any:
        """Encodes a response into a string format."""
        pass

    @staticmethod
    def decode(encoded_value: Any) -> dict:
        """Decodes a string back into a response dictionary."""
        pass


class CacheResponseEncoder:
    """A class to encode cache responses."""

    @staticmethod
    def encode(value: Any) -> str:
        """Encodes a response dictionary into a string format.

        Args:
            response (dict): The response dictionary to encode.

        Returns:
            str: The encoded response as a string.
        """
        if isinstance(value, BaseModel):
            serialized = json.dumps(value.model_dump())
        elif isinstance(value, list) and all(isinstance(i, BaseModel) for i in value):
            serialized = json.dumps([i.model_dump() for i in value])
        else:
            serialized = json.dumps(value)
        return str(serialized)

    @staticmethod
    def decode(encoded_response: str) -> dict:
        """Decodes a string back into a response dictionary.

        Args:
            encoded_response (str): The encoded response string.

        Returns:
            dict: The decoded response dictionary.
        """
        try:
            return json.loads(encoded_response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode response: {str(e)}") from e


class PickledEncoder:
    """A class to encode cache responses using pickle."""

    @staticmethod
    def encode(value: Any) -> bytes:
        """Encodes a response dictionary into a string format.

        Args:
            response (dict): The response dictionary to encode.

        Returns:
            str: The encoded response as a string.
        """
        return pickle.dumps(value)

    @staticmethod
    def decode(encoded_response: bytes) -> Any:
        """Decodes a string back into a response dictionary.

        Args:
            encoded_response (str): The encoded response string.

        Returns:
            dict: The decoded response dictionary.
        """
        try:
            return pickle.loads(encoded_response)  # noqa: S301
        except pickle.UnpicklingError as e:
            raise ValueError(f"Failed to decode response: {str(e)}") from e
