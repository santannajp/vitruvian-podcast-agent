"""
tests/test_dialogue_planner.py — Unit tests for planning/dialogue_planner.py
"""

import unittest
from unittest.mock import MagicMock, call

from chunking.chunker import Chunk
from llm.provider import LLMProvider
from planning.dialogue_planner import summarize_chunk, generate_outline, _join_summaries


def _make_mock_llm(response: str) -> LLMProvider:
    """Helper: create a mock LLMProvider returning a fixed response."""
    mock = MagicMock(spec=LLMProvider)
    mock.generate_script.return_value = response
    return mock


def _make_chunk(index: int = 0, heading: str = "Section", content: str = "Some content here.") -> Chunk:
    """Helper: create a Chunk directly (bypasses chunk_markdown)."""
    c = object.__new__(Chunk)
    c.index = index
    c.heading = heading
    c.content = content
    c.token_count = len(content.split())
    return c


class TestSummarizeChunk(unittest.TestCase):

    def test_returns_non_empty_string(self):
        chunk = _make_chunk(content="AI is transforming the world rapidly.")
        mock_llm = _make_mock_llm("AI is changing society in profound ways.")
        result = summarize_chunk(chunk, mock_llm, "en")
        self.assertIsInstance(result, str)
        self.assertTrue(result)

    def test_result_is_stripped(self):
        chunk = _make_chunk()
        mock_llm = _make_mock_llm("  Summary with spaces.  ")
        result = summarize_chunk(chunk, mock_llm, "en")
        self.assertEqual(result, "Summary with spaces.")

    def test_llm_called_with_language(self):
        chunk = _make_chunk()
        mock_llm = _make_mock_llm("Resumo aqui.")
        summarize_chunk(chunk, mock_llm, "pt-BR")
        args, kwargs = mock_llm.generate_script.call_args
        self.assertEqual(kwargs.get("language") or args[1], "pt-BR")

    def test_llm_called_with_chunk_content_in_prompt(self):
        chunk = _make_chunk(content="Content about space exploration.")
        mock_llm = _make_mock_llm("Space summary.")
        summarize_chunk(chunk, mock_llm, "en")
        args, kwargs = mock_llm.generate_script.call_args
        prompt = kwargs.get("markdown") or args[0]
        self.assertIn("Content about space exploration.", prompt)

    def test_empty_llm_response_raises_value_error(self):
        chunk = _make_chunk()
        mock_llm = _make_mock_llm("")
        with self.assertRaises(ValueError) as ctx:
            summarize_chunk(chunk, mock_llm, "en")
        self.assertIn("empty summary", str(ctx.exception))

    def test_whitespace_only_response_raises_value_error(self):
        chunk = _make_chunk()
        mock_llm = _make_mock_llm("   \n  ")
        with self.assertRaises(ValueError):
            summarize_chunk(chunk, mock_llm, "en")

    def test_runtime_error_from_llm_propagates(self):
        chunk = _make_chunk()
        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.generate_script.side_effect = RuntimeError("API down")
        with self.assertRaises(RuntimeError) as ctx:
            summarize_chunk(chunk, mock_llm, "en")
        self.assertIn("API down", str(ctx.exception))


class TestGenerateOutline(unittest.TestCase):

    SUMMARIES = [
        "Section 1 is about machine learning.",
        "Section 2 covers neural networks.",
        "Section 3 discusses applications.",
    ]

    def test_returns_non_empty_string(self):
        mock_llm = _make_mock_llm("1. Introduction\n2. Body\n3. Conclusion")
        result = generate_outline(self.SUMMARIES, mock_llm, "en")
        self.assertIsInstance(result, str)
        self.assertTrue(result)

    def test_result_is_stripped(self):
        mock_llm = _make_mock_llm("  Outline here.  ")
        result = generate_outline(self.SUMMARIES, mock_llm, "en")
        self.assertEqual(result, "Outline here.")

    def test_all_summaries_included_in_prompt(self):
        mock_llm = _make_mock_llm("Outline.")
        generate_outline(self.SUMMARIES, mock_llm, "en")
        args, kwargs = mock_llm.generate_script.call_args
        prompt = kwargs.get("markdown") or args[0]
        for summary in self.SUMMARIES:
            self.assertIn(summary, prompt)

    def test_language_passed_to_llm(self):
        mock_llm = _make_mock_llm("Roteiro.")
        generate_outline(self.SUMMARIES, mock_llm, "pt-BR")
        args, kwargs = mock_llm.generate_script.call_args
        self.assertEqual(kwargs.get("language") or args[1], "pt-BR")

    def test_empty_summaries_list_raises_value_error(self):
        mock_llm = _make_mock_llm("Outline.")
        with self.assertRaises(ValueError) as ctx:
            generate_outline([], mock_llm, "en")
        self.assertIn("empty summaries", str(ctx.exception))

    def test_empty_outline_response_raises_value_error(self):
        mock_llm = _make_mock_llm("")
        with self.assertRaises(ValueError) as ctx:
            generate_outline(self.SUMMARIES, mock_llm, "en")
        self.assertIn("empty outline", str(ctx.exception))

    def test_runtime_error_propagates(self):
        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.generate_script.side_effect = RuntimeError("timeout")
        with self.assertRaises(RuntimeError):
            generate_outline(self.SUMMARIES, mock_llm, "en")


class TestJoinSummaries(unittest.TestCase):

    def test_single_summary(self):
        result = _join_summaries(["Summary A."])
        self.assertIn("[Section 1]", result)
        self.assertIn("Summary A.", result)

    def test_multiple_summaries_numbered(self):
        result = _join_summaries(["First.", "Second.", "Third."])
        self.assertIn("[Section 1]", result)
        self.assertIn("[Section 2]", result)
        self.assertIn("[Section 3]", result)

    def test_summaries_joined_with_double_newline(self):
        result = _join_summaries(["A.", "B."])
        self.assertIn("\n\n", result)


if __name__ == "__main__":
    unittest.main()
