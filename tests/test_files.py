from io import BytesIO

import pandas as pd
import pytest

from fastspine.util.files import is_excel_file


@pytest.fixture
def excel_file() -> BytesIO:
    """Creates an in-memory Excel file containing a single sheet with email data.

    Returns:
        BytesIO: A BytesIO object containing the Excel file data.
    """
    data = {
        "Email": ["some@something.com"],
    }
    df = pd.DataFrame(data)
    file_data = BytesIO()
    df.to_excel(file_data, index=False)

    file_data.seek(0)

    return file_data


def test_is_excel_file(excel_file: BytesIO):
    """Test function to check if a given file is an Excel file.

    Args:
        excel_file (BytesIO): A BytesIO object representing the Excel file to be tested.
    Asserts:
        The function asserts that the is_excel_file function returns True for the given excel_file.
    """
    assert is_excel_file(excel_file) is True
