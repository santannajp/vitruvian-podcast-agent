"""
tests/test_script_generator.py — Unit tests for script/generator.py
"""

import unittest
from unittest.mock import MagicMock

from script.generator import generate_script, _validate_script_format
from llm.provider import LLMProvider


def _make_mock_llm(response: str) -> LLMProvider:
    """Helper: create a mock LLMProvider that returns a fixed response."""
    mock = MagicMock(spec=LLMProvider)
    mock.generate_script.return_value = response
    return mock


class TestValidateScriptFormat(unittest.TestCase):

    def test_valid_script_passes(self):
        script = "Host1: Hello!\nHost2: Hi there!"
        # Should not raise
        _validate_script_format(script)

    def test_script_without_host_lines_raises(self):
        with self.assertRaises(ValueError) as ctx:
            _validate_script_format("Just some text with no hosts.")
        self.assertIn("Host1:/Host2:", str(ctx.exception))

    def test_only_host1_lines_also_passes(self):
        script = "Host1: I'm the only one talking."
        _validate_script_format(script)

    def test_only_host2_lines_also_passes(self):
        script = "Host2: Just me here."
        _validate_script_format(script)


class TestGenerateScript(unittest.TestCase):

    VALID_SCRIPT = (
        "Host1: Welcome to the podcast!\n"
        "Host2: Thanks for having me.\n"
        "Host1: Today we discuss AI.\n"
        "Host2: Exciting topic!"
    )

    def test_returns_valid_script(self):
        mock_llm = _make_mock_llm(self.VALID_SCRIPT)
        result = generate_script("some markdown", "en", mock_llm)
        self.assertEqual(result, self.VALID_SCRIPT)

    def test_strips_whitespace_from_llm_output(self):
        mock_llm = _make_mock_llm("  \n" + self.VALID_SCRIPT + "\n  ")
        result = generate_script("some markdown", "en", mock_llm)
        self.assertEqual(result, self.VALID_SCRIPT)

    def test_empty_llm_response_raises_value_error(self):
        mock_llm = _make_mock_llm("")
        with self.assertRaises(ValueError) as ctx:
            generate_script("some markdown", "en", mock_llm)
        self.assertIn("empty script", str(ctx.exception))

    def test_whitespace_only_llm_response_raises_value_error(self):
        mock_llm = _make_mock_llm("   \n\n  ")
        with self.assertRaises(ValueError):
            generate_script("some markdown", "en", mock_llm)

    def test_malformed_script_raises_value_error(self):
        mock_llm = _make_mock_llm("This is not a dialogue.")
        with self.assertRaises(ValueError):
            generate_script("some markdown", "en", mock_llm)

    def test_llm_provider_called_with_correct_args(self):
        mock_llm = _make_mock_llm(self.VALID_SCRIPT)
        generate_script("my markdown content", "pt-BR", mock_llm)
        mock_llm.generate_script.assert_called_once_with(
            markdown="my markdown content",
            language="pt-BR",
        )

    def test_runtime_error_from_llm_propagates(self):
        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.generate_script.side_effect = RuntimeError("API down")
        with self.assertRaises(RuntimeError) as ctx:
            generate_script("some markdown", "en", mock_llm)
        self.assertIn("API down", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
