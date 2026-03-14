"""
input/handler.py — Input validation and normalization.

Validates and normalises raw user input before it enters the pipeline.
Returns an InputContent dataclass that subsequent stages consume.
"""

from dataclasses import dataclass
from enum import Enum


class SourceType(str, Enum):
    """Supported input source types."""
    TEXT = "text"
    URL = "url"
    FILE = "file"


@dataclass
class InputContent:
    """Structured representation of a validated user input."""
    source_type: SourceType
    source_value: str


def handle_input(raw_input: str) -> InputContent:
    """
    Validate and normalise a raw user input string.

    Detects whether the input is a URL, a file path, or plain text and
    returns a typed InputContent instance.

    Args:
        raw_input: The raw string provided by the user.

    Returns:
        InputContent with the detected source_type and normalised source_value.

    Raises:
        ValueError: If the input is empty or blank.
    """
    if not raw_input or not raw_input.strip():
        raise ValueError("Input must not be empty.")

    value = raw_input.strip()

    if _is_url(value):
        return InputContent(source_type=SourceType.URL, source_value=value)

    if _is_file_path(value):
        return InputContent(source_type=SourceType.FILE, source_value=value)

    return InputContent(source_type=SourceType.TEXT, source_value=value)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _is_url(value: str) -> bool:
    """Return True if value looks like a URL."""
    return value.startswith(("http://", "https://", "ftp://"))


def _is_file_path(value: str) -> bool:
    """Return True if value is an existing file path."""
    import os
    return os.path.isfile(value)
