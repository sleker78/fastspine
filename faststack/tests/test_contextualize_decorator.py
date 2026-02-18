import uuid
from unittest.mock import MagicMock, patch

import pytest

from ..decorators.contextualize_decorator import with_contextualize


def test_with_contextualize_basic_functionality():
    """Test basic functionality of with_contextualize decorator."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize()
        def sample_task(self):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self)

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Check that correlation_id and task_name were passed
        call_kwargs = mock_contextualize.call_args[1]
        assert "correlation_id" in call_kwargs
        assert call_kwargs["task_name"] == "sample_task"
        assert isinstance(call_kwargs["correlation_id"], str)


def test_with_contextualize_without_self_name():
    """Test decorator when self.name is not available."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize()
        def sample_task(self):
            return "task_result"

        mock_self = MagicMock(spec=[])  # MagicMock without name attribute

        result = sample_task(mock_self)

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Check that task_name falls back to function name
        call_kwargs = mock_contextualize.call_args[1]
        assert call_kwargs["task_name"] == "sample_task"


def test_with_contextualize_with_context_params_positional_args():
    """Test decorator with context params using positional arguments."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize(input_list_id="input_list_id", task_id="request_id")
        def sample_task(self, input_list_id, request_id, extra_param):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self, 123, 456, "extra")

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Check that context params were extracted from positional args
        call_kwargs = mock_contextualize.call_args[1]
        assert call_kwargs["input_list_id"] == 123
        assert call_kwargs["task_id"] == 456
        assert call_kwargs["task_name"] == "sample_task"


def test_with_contextualize_with_context_params_keyword_args():
    """Test decorator with context params using keyword arguments."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize(input_list_id="input_list_id", task_id="request_id")
        def sample_task(self, input_list_id, request_id, extra_param=None):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self, input_list_id=123, request_id=456, extra_param="extra")

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Check that context params were extracted from keyword args
        call_kwargs = mock_contextualize.call_args[1]
        assert call_kwargs["input_list_id"] == 123
        assert call_kwargs["task_id"] == 456


def test_with_contextualize_mixed_args():
    """Test decorator with mixed positional and keyword arguments."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize(input_list_id="input_list_id", task_id="request_id")
        def sample_task(self, input_list_id, request_id, extra_param=None):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self, 123, request_id=456, extra_param="extra")

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Check that context params were extracted correctly
        call_kwargs = mock_contextualize.call_args[1]
        assert call_kwargs["input_list_id"] == 123
        assert call_kwargs["task_id"] == 456


def test_with_contextualize_param_not_in_function_signature():
    """Test decorator when context param is not in function signature."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize(input_list_id="nonexistent_param")
        def sample_task(self, real_param):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self, "value")

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Check that only correlation_id and task_name are present
        call_kwargs = mock_contextualize.call_args[1]
        assert "input_list_id" not in call_kwargs
        assert "correlation_id" in call_kwargs
        assert call_kwargs["task_name"] == "sample_task"


def test_with_contextualize_insufficient_positional_args():
    """Test decorator when not enough positional arguments are provided."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize(input_list_id="input_list_id", task_id="request_id")
        def sample_task(self, input_list_id, request_id=None):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self, 123)  # Missing request_id

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Check that only available param is extracted
        call_kwargs = mock_contextualize.call_args[1]
        assert call_kwargs["input_list_id"] == 123
        assert "task_id" not in call_kwargs


def test_with_contextualize_preserves_function_metadata():
    """Test that the decorator preserves function metadata."""

    @with_contextualize(input_list_id="input_list_id")
    def sample_task(self, input_list_id):
        """This is a sample task function."""
        return "task_result"

    assert sample_task.__name__ == "sample_task"
    assert sample_task.__doc__ == "This is a sample task function."


def test_with_contextualize_correlation_id_uniqueness():
    """Test that each call generates a unique correlation_id."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize()
        def sample_task(self):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        # Call the function twice
        sample_task(mock_self)
        sample_task(mock_self)

        assert mock_contextualize.call_count == 2

        # Get correlation_ids from both calls
        first_call_kwargs = mock_contextualize.call_args_list[0][1]
        second_call_kwargs = mock_contextualize.call_args_list[1][1]

        assert first_call_kwargs["correlation_id"] != second_call_kwargs["correlation_id"]


def test_with_contextualize_uuid_format():
    """Test that correlation_id is a valid UUID string."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize()
        def sample_task(self):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        sample_task(mock_self)

        call_kwargs = mock_contextualize.call_args[1]
        correlation_id = call_kwargs["correlation_id"]

        # Verify it's a valid UUID string
        uuid.UUID(correlation_id)  # Should not raise an exception


def test_with_contextualize_context_manager_usage():
    """Test that contextualize is used as a context manager."""
    mock_contextualize = MagicMock()
    mock_context = MagicMock()
    mock_contextualize.return_value = mock_context

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize()
        def sample_task(self):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self)

        assert result == "task_result"
        mock_context.__enter__.assert_called_once()
        mock_context.__exit__.assert_called_once()


def test_with_contextualize_exception_handling():
    """Test that exceptions are properly propagated through the context manager."""
    mock_contextualize = MagicMock()
    mock_context = MagicMock()
    mock_contextualize.return_value = mock_context

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize()
        def failing_task(self):
            raise ValueError("Task failed")

        mock_self = MagicMock()
        mock_self.name = "module.failing_task"

        with pytest.raises(ValueError, match="Task failed"):
            failing_task(mock_self)

        # Context manager should still be properly entered and exited
        mock_context.__enter__.assert_called_once()
        mock_context.__exit__.assert_called_once()


def test_with_contextualize_no_context_params():
    """Test decorator without any context parameters."""
    mock_contextualize = MagicMock()

    with patch("faststack.decorators.contextualize_decorator.contextualize", mock_contextualize):

        @with_contextualize()
        def sample_task(self, param1, param2):
            return "task_result"

        mock_self = MagicMock()
        mock_self.name = "module.sample_task"

        result = sample_task(mock_self, "value1", "value2")

        assert result == "task_result"
        mock_contextualize.assert_called_once()

        # Only correlation_id and task_name should be present
        call_kwargs = mock_contextualize.call_args[1]
        assert len(call_kwargs) == 2
        assert "correlation_id" in call_kwargs
        assert call_kwargs["task_name"] == "sample_task"
