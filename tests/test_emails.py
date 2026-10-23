import pytest

from fastspine.util.emails import is_valid_email


@pytest.mark.parametrize(
    "email",
    [
        "test@example.com",
        "user.name+tag+sorting@example.com",
        "user_name@example.co.uk",
        "user-name@example.org",
        "user.name@example.com",
    ],
)
def test_valid_email(email):
    """Test if the provided email is valid.

    Args:
        email (str): The email address to be validated.
    Asserts:
        bool: True if the email is valid, False otherwise.
    """
    assert is_valid_email(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "plainaddress",
        "@missingusername.com",
        "username@.com",
        "username@.com.",
        "username@com",
        "username@-example.com",
        "username@example..com",
    ],
)
def test_invalid_email(email):
    """Test case for checking invalid email addresses.

    Args:
        email (str): The email address to be tested.
    Asserts:
        The function asserts that the provided email address is invalid by
        checking that is_valid_email(email) returns False.
    """
    assert is_valid_email(email) is False
