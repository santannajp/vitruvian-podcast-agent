"""
tests/test_input_handler.py — Unit tests for input/handler.py
"""

import unittest
from unittest.mock import patch
import os

from input.handler import handle_input, SourceType, InputContent


class TestHandleInput(unittest.TestCase):

    # ------------------------------------------------------------------
    # Empty / blank input
    # ------------------------------------------------------------------

    def test_raises_on_empty_string(self):
        with self.assertRaises(ValueError):
            handle_input("")

    def test_raises_on_blank_string(self):
        with self.assertRaises(ValueError):
            handle_input("   ")

    # ------------------------------------------------------------------
    # URL detection
    # ------------------------------------------------------------------

    def test_detects_http_url(self):
        result = handle_input("http://example.com")
        self.assertEqual(result.source_type, SourceType.URL)
        self.assertEqual(result.source_value, "http://example.com")

    def test_detects_https_url(self):
        result = handle_input("https://example.com/article")
        self.assertEqual(result.source_type, SourceType.URL)

    def test_detects_ftp_url(self):
        result = handle_input("ftp://files.example.com/data.txt")
        self.assertEqual(result.source_type, SourceType.URL)

    # ------------------------------------------------------------------
    # File path detection (mocked)
    # ------------------------------------------------------------------

    def test_detects_existing_file_path(self):
        with patch("os.path.isfile", return_value=True):
            result = handle_input("/some/existing/file.txt")
        self.assertEqual(result.source_type, SourceType.FILE)
        self.assertEqual(result.source_value, "/some/existing/file.txt")

    def test_non_existing_path_treated_as_text(self):
        with patch("os.path.isfile", return_value=False):
            result = handle_input("/not/a/real/file.txt")
        self.assertEqual(result.source_type, SourceType.TEXT)

    # ------------------------------------------------------------------
    # Plain text detection
    # ------------------------------------------------------------------

    def test_detects_plain_text(self):
        result = handle_input("This is some plain text content.")
        self.assertEqual(result.source_type, SourceType.TEXT)
        self.assertEqual(result.source_value, "This is some plain text content.")

    def test_strips_leading_trailing_whitespace(self):
        result = handle_input("  hello world  ")
        self.assertEqual(result.source_value, "hello world")

    # ------------------------------------------------------------------
    # Return type
    # ------------------------------------------------------------------

    def test_returns_input_content_instance(self):
        result = handle_input("some text")
        self.assertIsInstance(result, InputContent)


if __name__ == "__main__":
    unittest.main()
