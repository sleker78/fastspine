import re
from io import BytesIO


def is_excel_file(file: BytesIO) -> bool:
    """Check if the given file is an Excel file based on its MIME type.

    Args:
        file (BytesIO): The file to check, provided as a BytesIO object.

    Returns:
        bool: True if the file is an Excel file, False otherwise.
    """
    file.seek(0)
    file_start = file.read(8)
    # XLS signature (Excel 97-2003)
    xls_signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

    # XLSX signature (Excel 2007 and later)
    xlsx_signature = b"PK\x03\x04"

    return file_start == xls_signature or file_start.startswith(xlsx_signature)


def sanitize_filename(filename: str, max_length: int = 255) -> str:
    """Sanitize filename by removing unsafe characters and limiting length."""
    filename = filename.strip().replace(" ", "_")  # Replace spaces with underscores
    filename = re.sub(r'[\/:*?"<>|]', "", filename)  # Remove unsafe characters
    return filename[:max_length]  # Limit filename lengt
