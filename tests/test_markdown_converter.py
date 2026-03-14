"""
tests/test_markdown_converter.py — Unit tests for markdown/converter.py
"""

import unittest
from unittest.mock import patch, MagicMock

from input.handler import InputContent, SourceType
from markdown.converter import convert_to_markdown, _normalize_text


class TestNormalizeText(unittest.TestCase):

    def test_strips_trailing_whitespace_per_line(self):
        raw = "hello   \nworld  "
        result = _normalize_text(raw)
        self.assertEqual(result, "hello\nworld")

    def test_strips_leading_and_trailing_blank_lines(self):
        raw = "\n\nhello\n\n"
        result = _normalize_text(raw)
        self.assertEqual(result, "hello")

    def test_empty_string_returns_empty(self):
        result = _normalize_text("")
        self.assertEqual(result, "")

    def test_multiline_preserved(self):
        raw = "line one\nline two\nline three"
        result = _normalize_text(raw)
        self.assertEqual(result, "line one\nline two\nline three")


class TestConvertToMarkdown(unittest.TestCase):

    # ------------------------------------------------------------------
    # TEXT source (no external calls)
    # ------------------------------------------------------------------

    def test_text_source_normalizes_text(self):
        content = InputContent(source_type=SourceType.TEXT, source_value="  hello  \nworld  ")
        result = convert_to_markdown(content)
        self.assertEqual(result, "hello\nworld")

    def test_text_source_plain_passthrough(self):
        content = InputContent(source_type=SourceType.TEXT, source_value="simple text")
        result = convert_to_markdown(content)
        self.assertEqual(result, "simple text")

    # ------------------------------------------------------------------
    # URL / FILE source — MarkItDown mocked
    # ------------------------------------------------------------------

    def _mock_markitdown(self, text_content: str) -> tuple:
        """Return (sys.modules patch, md_instance mock) for markitdown."""
        mock_result = MagicMock()
        mock_result.text_content = text_content
        mock_md_instance = MagicMock()
        mock_md_instance.convert.return_value = mock_result
        mock_markitdown_module = MagicMock()
        mock_markitdown_module.MarkItDown.return_value = mock_md_instance
        return mock_markitdown_module, mock_md_instance

    def test_url_source_calls_markitdown(self):
        mock_module, mock_md_instance = self._mock_markitdown("# Converted Markdown")

        with patch.dict("sys.modules", {"markitdown": mock_module}):
            content = InputContent(source_type=SourceType.URL, source_value="https://example.com")
            result = convert_to_markdown(content)

        self.assertEqual(result, "# Converted Markdown")
        mock_md_instance.convert.assert_called_once_with("https://example.com")

    def test_file_source_calls_markitdown(self):
        mock_module, mock_md_instance = self._mock_markitdown("# File Content")

        with patch.dict("sys.modules", {"markitdown": mock_module}):
            content = InputContent(source_type=SourceType.FILE, source_value="/path/to/doc.pdf")
            result = convert_to_markdown(content)

        self.assertEqual(result, "# File Content")

    def test_markitdown_failure_raises_runtime_error(self):
        mock_markitdown_module = MagicMock()
        mock_markitdown_module.MarkItDown.side_effect = Exception("boom")

        with patch.dict("sys.modules", {"markitdown": mock_markitdown_module}):
            content = InputContent(source_type=SourceType.URL, source_value="https://fail.com")
            with self.assertRaises(RuntimeError) as ctx:
                convert_to_markdown(content)
        self.assertIn("MarkItDown conversion failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
