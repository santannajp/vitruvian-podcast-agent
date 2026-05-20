"""
tests/test_script_generator_hierarchical.py — Unit tests for
generate_script_hierarchical() in script/generator.py
"""

import unittest
from unittest.mock import MagicMock, patch

from chunking.chunker import Chunk
from llm.provider import LLMProvider
from script.generator import generate_script, generate_script_hierarchical


VALID_DIALOGUE = (
    "Host1: Welcome to the podcast!\n"
    "Host2: Thanks for having me.\n"
    "Host1: Today we discuss AI.\n"
    "Host2: Exciting topic!"
)


def _make_chunk(index: int, heading: str = "Section", content: str = "Some content.") -> Chunk:
    """Build a Chunk directly without calling chunk_markdown."""
    c = object.__new__(Chunk)
    c.index = index
    c.heading = heading
    c.content = content
    c.token_count = len(content.split())
    return c


def _make_mock_llm_sequence(*responses: str) -> LLMProvider:
    """Return a mock LLM whose generate_script yields responses in order."""
    mock = MagicMock(spec=LLMProvider)
    mock.generate_script.side_effect = list(responses)
    return mock


class TestGenerateScriptHierarchical(unittest.TestCase):

    def _get_chunks(self, n: int = 2) -> list:
        return [_make_chunk(i, heading=f"Section {i+1}", content=f"Content for section {i+1}.") for i in range(n)]

    # For 2 chunks the LLM is called:
    #   1 × per chunk (summaries) + 1 × outline + 1 × final dialogue = 4 calls
    def _responses_for(self, n_chunks: int, dialogue: str = VALID_DIALOGUE) -> tuple:
        summaries = [f"Summary of section {i+1}." for i in range(n_chunks)]
        outline = "1. Intro\n2. Main\n3. Conclusion"
        return (*summaries, outline, dialogue)

    def test_returns_valid_script(self):
        chunks = self._get_chunks(2)
        mock_llm = _make_mock_llm_sequence(*self._responses_for(2))
        result = generate_script_hierarchical(chunks, mock_llm, "en")
        self.assertEqual(result, VALID_DIALOGUE)

    def test_script_contains_host_lines(self):
        chunks = self._get_chunks(2)
        mock_llm = _make_mock_llm_sequence(*self._responses_for(2))
        result = generate_script_hierarchical(chunks, mock_llm, "en")
        lines = [l.strip() for l in result.splitlines() if l.strip()]
        host_lines = [l for l in lines if l.startswith("Host1:") or l.startswith("Host2:")]
        self.assertGreater(len(host_lines), 0)

    def test_llm_called_correct_number_of_times(self):
        n = 3
        chunks = self._get_chunks(n)
        mock_llm = _make_mock_llm_sequence(*self._responses_for(n))
        generate_script_hierarchical(chunks, mock_llm, "en")
        # n summaries + 1 outline + 1 final = n + 2
        self.assertEqual(mock_llm.generate_script.call_count, n + 2)

    def test_language_code_passed_to_all_llm_calls(self):
        chunks = self._get_chunks(2)
        mock_llm = _make_mock_llm_sequence(*self._responses_for(2))
        generate_script_hierarchical(chunks, mock_llm, "pt-BR")
        for c in mock_llm.generate_script.call_args_list:
            args, kwargs = c
            lang = kwargs.get("language") or args[1]
            self.assertEqual(lang, "pt-BR")

    def test_empty_chunks_list_raises_value_error(self):
        mock_llm = MagicMock(spec=LLMProvider)
        with self.assertRaises(ValueError) as ctx:
            generate_script_hierarchical([], mock_llm, "en")
        self.assertIn("chunks list must not be empty", str(ctx.exception))

    def test_empty_final_script_raises_value_error(self):
        chunks = self._get_chunks(1)
        # summary + outline + empty final dialogue
        mock_llm = _make_mock_llm_sequence("Summary.", "1. Outline.", "")
        with self.assertRaises(ValueError) as ctx:
            generate_script_hierarchical(chunks, mock_llm, "en")
        self.assertIn("empty script", str(ctx.exception))

    def test_malformed_final_script_raises_value_error(self):
        chunks = self._get_chunks(1)
        mock_llm = _make_mock_llm_sequence("Summary.", "1. Outline.", "Not a dialogue at all.")
        with self.assertRaises(ValueError):
            generate_script_hierarchical(chunks, mock_llm, "en")

    def test_runtime_error_in_summary_stage_propagates(self):
        chunks = self._get_chunks(2)
        mock_llm = MagicMock(spec=LLMProvider)
        mock_llm.generate_script.side_effect = RuntimeError("API down during summarise")
        with self.assertRaises(RuntimeError) as ctx:
            generate_script_hierarchical(chunks, mock_llm, "en")
        self.assertIn("API down", str(ctx.exception))

    def test_runtime_error_in_outline_stage_propagates(self):
        chunks = self._get_chunks(1)
        mock_llm = _make_mock_llm_sequence("Summary.")
        mock_llm.generate_script.side_effect = [
            "Summary.",
            RuntimeError("API down during outline"),
        ]
        with self.assertRaises(RuntimeError):
            generate_script_hierarchical(chunks, mock_llm, "en")

    def test_strips_whitespace_from_final_script(self):
        chunks = self._get_chunks(1)
        padded = "  \n" + VALID_DIALOGUE + "\n  "
        mock_llm = _make_mock_llm_sequence("Summary.", "1. Outline.", padded)
        result = generate_script_hierarchical(chunks, mock_llm, "en")
        self.assertEqual(result, VALID_DIALOGUE)


class TestGenerateScriptRegressionCheck(unittest.TestCase):
    """Verify that the original generate_script() still works after Phase 2 changes."""

    def test_simple_pipeline_still_works(self):
        mock = MagicMock(spec=LLMProvider)
        mock.generate_script.return_value = VALID_DIALOGUE
        result = generate_script("some markdown", "en", mock)
        self.assertEqual(result, VALID_DIALOGUE)

    def test_simple_pipeline_raises_on_empty(self):
        mock = MagicMock(spec=LLMProvider)
        mock.generate_script.return_value = ""
        with self.assertRaises(ValueError):
            generate_script("some markdown", "en", mock)

    def test_simple_pipeline_raises_on_malformed(self):
        mock = MagicMock(spec=LLMProvider)
        mock.generate_script.return_value = "Not a dialogue."
        with self.assertRaises(ValueError):
            generate_script("some markdown", "en", mock)


if __name__ == "__main__":
    unittest.main()
