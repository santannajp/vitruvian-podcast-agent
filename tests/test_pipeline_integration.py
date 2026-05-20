"""
tests/test_pipeline_integration.py — Integration tests for the full pipeline.

Tests the complete Content → Podcast pipeline end-to-end with all external
services mocked (Ollama, Piper, MarkItDown, pydub export).

These tests validate that the stages are correctly wired together:
    Input → Markdown → Language Detection → Script Generation → TTS → MP3
"""

import io
import sys
import unittest
from unittest.mock import MagicMock, patch

from pydub import AudioSegment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_SCRIPT = (
    "Host1: Welcome to the podcast!\n"
    "Host2: Great to be here.\n"
    "Host1: Today we talk about artificial intelligence.\n"
    "Host2: Fascinating topic!"
)


def _silent_wav(duration_ms: int = 100) -> bytes:
    """Produce minimal silent WAV bytes for mocking TTS output."""
    silence = AudioSegment.silent(duration=duration_ms)
    buf = io.BytesIO()
    silence.export(buf, format="wav")
    return buf.getvalue()


def _make_mock_llm(script: str = VALID_SCRIPT) -> MagicMock:
    from llm.provider import LLMProvider
    mock = MagicMock(spec=LLMProvider)
    mock.generate_script.return_value = script
    return mock


def _make_mock_tts() -> MagicMock:
    from tts.provider import TTSProvider
    mock = MagicMock(spec=TTSProvider)
    mock.synthesize.return_value = _silent_wav()
    return mock


# ---------------------------------------------------------------------------
# Integration: simple pipeline (short content)
# ---------------------------------------------------------------------------

class TestSimplePipelineIntegration(unittest.TestCase):
    """Full pipeline with short content (no chunking)."""

    def test_text_input_produces_mp3(self):
        """Given plain text, the pipeline should produce a podcast MP3."""
        from app.main import run_pipeline

        mock_llm = _make_mock_llm()
        mock_tts = _make_mock_tts()

        with patch("app.main.build_llm_provider", return_value=mock_llm), \
             patch("app.main.build_tts_provider", return_value=mock_tts), \
             patch("app.main._estimate_tokens", return_value=100), \
             patch("audio.builder.AudioSegment.export") as mock_export, \
             patch("language.detector.detect", return_value="en"):

            result = run_pipeline("Artificial intelligence is transforming the world.")

        self.assertIsNotNone(result)
        mock_export.assert_called_once()
        call_args = mock_export.call_args
        # export(output_path, format="mp3") — format is a keyword argument
        self.assertEqual(call_args.kwargs.get("format") or call_args[1].get("format"), "mp3")

    def test_language_propagates_from_detection_to_tts(self):
        """Language detected in stage 3 must reach the TTS provider."""
        from app.main import run_pipeline

        mock_llm = _make_mock_llm()
        mock_tts = _make_mock_tts()

        with patch("app.main.build_llm_provider", return_value=mock_llm), \
             patch("app.main.build_tts_provider", return_value=mock_tts), \
             patch("app.main._estimate_tokens", return_value=100), \
             patch("audio.builder.AudioSegment.export"), \
             patch("language.detector.detect", return_value="es"):

            run_pipeline("La inteligencia artificial está transformando el mundo.")

        # Every synthesize call should carry the detected language
        for call in mock_tts.synthesize.call_args_list:
            _, kwargs = call
            self.assertEqual(kwargs["language"], "es")

    def test_llm_receives_markdown_content(self):
        """The LLM provider must receive Markdown-formatted content."""
        from app.main import run_pipeline

        mock_llm = _make_mock_llm()
        mock_tts = _make_mock_tts()

        raw_text = "  Hello   \nworld  "

        with patch("app.main.build_llm_provider", return_value=mock_llm), \
             patch("app.main.build_tts_provider", return_value=mock_tts), \
             patch("app.main._estimate_tokens", return_value=100), \
             patch("audio.builder.AudioSegment.export"), \
             patch("language.detector.detect", return_value="en"):

            run_pipeline(raw_text)

        # generate_script must have been called with some markdown text
        mock_llm.generate_script.assert_called_once()
        call_kwargs = mock_llm.generate_script.call_args[1]
        self.assertIn("markdown", call_kwargs)
        self.assertIn("language", call_kwargs)

    def test_empty_input_raises_value_error(self):
        """Empty input should be caught by the input handler."""
        from app.main import run_pipeline

        with self.assertRaises((ValueError, RuntimeError)):
            run_pipeline("")


# ---------------------------------------------------------------------------
# Integration: hierarchical pipeline (long content)
# ---------------------------------------------------------------------------

class TestHierarchicalPipelineIntegration(unittest.TestCase):
    """Full pipeline with long content that triggers chunking."""

    # 3 chunks × (1 summary + 1 outline + 1 dialogue) = n_chunks + 2 LLM calls
    N_CHUNKS = 2

    def _responses_for(self, n_chunks: int) -> list:
        summaries = [f"Summary {i + 1}." for i in range(n_chunks)]
        outline = "1. Intro\n2. Main\n3. Conclusion"
        return [*summaries, outline, VALID_SCRIPT]

    def test_long_content_triggers_hierarchical_pipeline(self):
        """Content exceeding the threshold should use the chunking pipeline."""
        from app.main import run_pipeline
        from chunking.chunker import Chunk

        def _make_chunk(idx: int) -> Chunk:
            c = object.__new__(Chunk)
            c.index = idx
            c.heading = f"Section {idx}"
            c.content = "Some content."
            c.token_count = 10
            return c

        fake_chunks = [_make_chunk(i) for i in range(self.N_CHUNKS)]

        mock_llm = MagicMock()
        mock_llm.generate_script.side_effect = self._responses_for(self.N_CHUNKS)
        mock_tts = _make_mock_tts()

        with patch("app.main.build_llm_provider", return_value=mock_llm), \
             patch("app.main.build_tts_provider", return_value=mock_tts), \
             patch("app.main._estimate_tokens", return_value=99999), \
             patch("app.main.chunk_markdown", return_value=fake_chunks), \
             patch("audio.builder.AudioSegment.export"), \
             patch("language.detector.detect", return_value="en"):

            result = run_pipeline("A very long document " * 300)

        # n_chunks summaries + 1 outline + 1 final dialogue
        self.assertEqual(
            mock_llm.generate_script.call_count,
            self.N_CHUNKS + 2,
        )
        self.assertIsNotNone(result)

    def test_hierarchical_pipeline_language_propagates(self):
        """Language code must be forwarded through the hierarchical pipeline."""
        from app.main import run_pipeline
        from chunking.chunker import Chunk

        def _make_chunk(idx: int) -> Chunk:
            c = object.__new__(Chunk)
            c.index = idx
            c.heading = f"Section {idx}"
            c.content = "Contenido."
            c.token_count = 10
            return c

        fake_chunks = [_make_chunk(i) for i in range(2)]
        mock_llm = MagicMock()
        mock_llm.generate_script.side_effect = self._responses_for(2)
        mock_tts = _make_mock_tts()

        with patch("app.main.build_llm_provider", return_value=mock_llm), \
             patch("app.main.build_tts_provider", return_value=mock_tts), \
             patch("app.main._estimate_tokens", return_value=99999), \
             patch("app.main.chunk_markdown", return_value=fake_chunks), \
             patch("audio.builder.AudioSegment.export"), \
             patch("language.detector.detect", return_value="es"):

            run_pipeline("Un documento muy largo " * 300)

        # Every LLM call must use the detected language
        for call in mock_llm.generate_script.call_args_list:
            _, kwargs = call
            self.assertEqual(kwargs.get("language"), "es")

        # Every TTS synthesize call must also use the detected language
        for call in mock_tts.synthesize.call_args_list:
            _, kwargs = call
            self.assertEqual(kwargs["language"], "es")


# ---------------------------------------------------------------------------
# Integration: provider builder functions
# ---------------------------------------------------------------------------

class TestProviderBuilders(unittest.TestCase):
    """Validate that build_llm_provider and build_tts_provider instantiate correctly."""

    def test_build_llm_provider_ollama(self):
        from app.main import build_llm_provider
        from llm.ollama_provider import OllamaProvider

        with patch("config.LLM_PROVIDER", "ollama"):
            provider = build_llm_provider()
        self.assertIsInstance(provider, OllamaProvider)

    def test_build_llm_provider_unknown_raises_value_error(self):
        from app.main import build_llm_provider

        with patch("config.LLM_PROVIDER", "unknown_provider"):
            with self.assertRaises(ValueError) as ctx:
                build_llm_provider()
        self.assertIn("unknown_provider", str(ctx.exception))

    def test_build_tts_provider_unknown_raises_value_error(self):
        from app.main import build_tts_provider

        with patch("config.TTS_PROVIDER", "unknown_provider"):
            with self.assertRaises(ValueError) as ctx:
                build_tts_provider()
        self.assertIn("unknown_provider", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
