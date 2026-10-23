import re


def is_valid_email(email: str) -> bool:
    """Validate the email address using a regular expression.

    Args:
        email (str): The email address to validate.

    Returns:
        bool: True if the email address is valid, False otherwise.
    """
    email_regex = r"^(?!.*\.\.)(?!.*\.$)(?!.*\.\.$)(?!.*@-)[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
    return re.match(email_regex, email) is not None
