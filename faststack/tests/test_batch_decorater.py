from unittest.mock import Mock, call, patch

import pytest
from sqlalchemy.exc import OperationalError

from ..decorators.upsert_decorator import upsert_decorator


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy session."""
    return Mock()


@pytest.fixture
def sample_data():
    """Sample data for testing."""
    return [
        {"id": 1, "name": "Frank", "email": "frank@example.com"},
        {"id": 2, "name": "JB", "email": "jb@example.com"},
        {"id": 3, "name": "Alex", "email": "alex@example.com"},
    ]


def test_basic_functionality(mock_session, sample_data):
    """Test basic decorator functionality."""
    mock_stmt = Mock()

    @upsert_decorator(batch_size=2)
    def test_upsert(session, batch):
        return mock_stmt

    test_upsert(mock_session, sample_data)

    # Should be called twice (3 items with batch_size=2)
    assert mock_session.execute.call_count == 2
    assert mock_session.commit.call_count == 2

    # Check that execute was called with our mock statement
    mock_session.execute.assert_called_with(mock_stmt)


def test_empty_data(mock_session):
    """Test that empty data doesn't execute anything."""

    @upsert_decorator()
    def test_upsert(session, batch):
        return Mock()

    test_upsert(mock_session, [])

    mock_session.execute.assert_not_called()
    mock_session.commit.assert_not_called()


def test_batch_size_parameter(mock_session, sample_data):
    """Test that batch_size parameter works correctly."""

    @upsert_decorator(batch_size=1)
    def test_upsert(session, batch):
        assert len(batch) == 1  # Each batch should have only 1 item
        return Mock()

    test_upsert(mock_session, sample_data)

    # With batch_size=1 and 3 items, should execute 3 times
    assert mock_session.execute.call_count == 3
    assert mock_session.commit.call_count == 3


def test_sort_key_functionality(mock_session):
    """Test that sort_key parameter works."""
    data = [
        {"name": "Jean-Baptiste", "id": 3},
        {"name": "Frank", "id": 1},
        {"name": "Alexandar", "id": 2},
    ]

    received_batches = []

    @upsert_decorator(batch_size=10, sort_key=lambda x: x["name"])
    def test_upsert(session, batch):
        received_batches.append(batch)
        return Mock()

    test_upsert(mock_session, data)

    # Data should be sorted by name
    sorted_batch = received_batches[0]
    assert sorted_batch[0]["name"] == "Alexandar"
    assert sorted_batch[1]["name"] == "Frank"
    assert sorted_batch[2]["name"] == "Jean-Baptiste"


def test_runtime_parameter_override(mock_session, sample_data):
    """Test that decorator parameters can be overridden at runtime."""

    @upsert_decorator(batch_size=10)  # Default batch size
    def test_upsert(session, batch):
        return Mock()

    # Override batch_size at runtime
    test_upsert(mock_session, sample_data, batch_size=1)

    # Should execute 3 times with batch_size=1
    assert mock_session.execute.call_count == 3


@patch("time.sleep")
def test_deadlock_retry_success(mock_sleep, mock_session, sample_data):
    """Test successful retry after deadlock."""
    mock_stmt = Mock()

    # First call raises deadlock, second succeeds
    mock_session.execute.side_effect = [
        OperationalError("deadlock detected", None, None),
        None,  # Success on retry
    ]

    @upsert_decorator(batch_size=10, max_attempts=3)
    def test_upsert(session, batch):
        return mock_stmt

    test_upsert(mock_session, sample_data)

    # Should be called twice (once failed, once succeeded)
    assert mock_session.execute.call_count == 2
    assert mock_session.rollback.call_count == 1
    assert mock_session.commit.call_count == 1
    mock_sleep.assert_called_once_with(0.1)  # Exponential backoff


@patch("time.sleep")
def test_deadlock_retry_exhausted(mock_sleep, mock_session, sample_data):
    """Test that exception is raised when max_attempts is exhausted."""
    mock_stmt = Mock()

    # Always raise deadlock
    mock_session.execute.side_effect = OperationalError("deadlock detected", None, None)

    @upsert_decorator(batch_size=10, max_attempts=2)
    def test_upsert(session, batch):
        return mock_stmt

    with pytest.raises(OperationalError):
        test_upsert(mock_session, sample_data)

    # Should try max_attempts times
    assert mock_session.execute.call_count == 2
    # Rollback is called only max_attempts - 1 times (not on the last failed attempt)
    assert mock_session.rollback.call_count == 1
    assert mock_session.commit.call_count == 0


@patch("time.sleep")
def test_exponential_backoff(mock_sleep, mock_session, sample_data):
    """Test exponential backoff timing."""
    mock_stmt = Mock()

    # Fail 3 times, succeed on 4th
    mock_session.execute.side_effect = [
        OperationalError("deadlock detected", None, None),
        OperationalError("deadlock detected", None, None),
        OperationalError("deadlock detected", None, None),
        None,  # Success
    ]

    @upsert_decorator(batch_size=10, max_attempts=5)
    def test_upsert(session, batch):
        return mock_stmt

    test_upsert(mock_session, sample_data)

    # Check exponential backoff: 0.1, 0.2, 0.4
    expected_calls = [call(0.1), call(0.2), call(0.4)]
    mock_sleep.assert_has_calls(expected_calls)


def test_non_deadlock_error_not_retried(mock_session, sample_data):
    """Test that non-deadlock errors are not retried."""
    mock_stmt = Mock()

    # Raise a different operational error
    mock_session.execute.side_effect = OperationalError("connection timeout", None, None)

    @upsert_decorator(batch_size=10, max_attempts=3)
    def test_upsert(session, batch):
        return mock_stmt

    with pytest.raises(OperationalError):
        test_upsert(mock_session, sample_data)

    # Should only try once (no retry for non-deadlock errors)
    assert mock_session.execute.call_count == 1
    # No rollback for non-deadlock errors (exception is re-raised immediately)
    assert mock_session.rollback.call_count == 0


def test_function_arguments_passed_through(mock_session, sample_data):
    """Test that additional function arguments are passed through."""
    received_args = []
    received_kwargs = []

    @upsert_decorator(batch_size=10)
    def test_upsert(session, batch, extra_arg, extra_kwarg=None):
        received_args.append(extra_arg)
        received_kwargs.append(extra_kwarg)
        return Mock()

    test_upsert(mock_session, sample_data, "test_arg", extra_kwarg="test_kwarg")

    assert received_args == ["test_arg"]
    assert received_kwargs == ["test_kwarg"]


def test_decorator_preserves_function_metadata(mock_session):
    """Test that decorator preserves original function metadata."""

    @upsert_decorator()
    def test_function_with_docstring(session, batch):
        """This is a test function."""
        return Mock()

    assert test_function_with_docstring.__name__ == "test_function_with_docstring"
    assert test_function_with_docstring.__doc__ == "This is a test function."


def test_multiple_batches_independent_retries(mock_session):
    """Test that each batch has independent retry logic."""
    data = list(range(25))  # 25 items

    call_count = 0

    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Fail on first batch's first attempt, succeed otherwise
        if call_count == 1:
            raise OperationalError("deadlock detected", None, None)
        return

    mock_session.execute.side_effect = side_effect

    @upsert_decorator(batch_size=10, max_attempts=3)
    def test_upsert(session, batch):
        return Mock()

    test_upsert(mock_session, data)

    # Should process 3 batches (10, 10, 5 items)
    # First batch: 2 attempts (1 fail, 1 success)
    # Second batch: 1 attempt (success)
    # Third batch: 1 attempt (success)
    # Total: 4 execute calls
    assert mock_session.execute.call_count == 4
    assert mock_session.commit.call_count == 3  # 3 successful batches
    assert mock_session.rollback.call_count == 1  # 1 rollback from first batch


def test_special_issue_authors_integration(mock_session):
    """Test the decorator works with the original use case."""
    # Mock the SQLAlchemy insert and model
    mock_insert = Mock()
    mock_stmt = Mock()
    mock_insert.return_value = mock_stmt
    mock_stmt.on_conflict_do_update.return_value = mock_stmt

    class SpecialIssueAuthor:
        email = Mock()

    @upsert_decorator(batch_size=2, sort_key=lambda x: x["email"])
    def upsert_special_issue_authors(session, batch):
        stmt = mock_insert(SpecialIssueAuthor).values(batch)
        return stmt.on_conflict_do_update(
            index_elements=[SpecialIssueAuthor.email],
            set_={
                "h_index": stmt.excluded.h_index,
                "papers": stmt.excluded.papers,
                "name": stmt.excluded.name,
            },
        )

    authors_data = [
        {"email": "author1@example.com", "h_index": 10, "papers": 50, "name": "Author 1"},
        {"email": "author2@example.com", "h_index": 15, "papers": 75, "name": "Author 2"},
        {"email": "author3@example.com", "h_index": 8, "papers": 30, "name": "Author 3"},
    ]

    upsert_special_issue_authors(mock_session, authors_data)

    # Should process 2 batches (2 items, 1 item)
    assert mock_session.execute.call_count == 2
    assert mock_session.commit.call_count == 2


def test_upsert_with_different_model(mock_session):
    """Test decorator with a different model structure."""
    mock_insert = Mock()
    mock_stmt = Mock()
    mock_insert.return_value = mock_stmt
    mock_stmt.on_conflict_do_update.return_value = mock_stmt

    @upsert_decorator(batch_size=5)
    def upsert_users(session, batch):
        return mock_stmt

    users_data = [{"id": i, "name": f"User {i}"} for i in range(12)]

    upsert_users(mock_session, users_data)

    # Should process 3 batches (5, 5, 2 items)
    assert mock_session.execute.call_count == 3
    assert mock_session.commit.call_count == 3
