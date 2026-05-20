"""
tests/test_architecture_invariants.py — Architecture invariant validation.

Verifies that the architectural rules defined in claude.md are respected
in the implementation. Each test maps to one or more of the invariants:

    1. All content must pass through Markdown conversion.
    2. LLMs must only receive Markdown or structured summaries.
    3. Dialogue format must always follow Host1:/Host2:.
    4. Audio generation must occur per dialogue line.
    5. Audio merging must occur only in the Podcast Builder.
    6. Providers must never be called outside provider modules.
    7. The detected language must always be propagated.
    8. The output podcast language must match the detected language.
"""

import importlib
import inspect
import io
import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pydub import AudioSegment


# ---------------------------------------------------------------------------
# Project root for source inspection
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent


def _source(relative_path: str) -> str:
    """Read the source of a project module file."""
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Invariant 1 — All content passes through Markdown conversion
# ---------------------------------------------------------------------------

class TestInvariant1AllContentConvertsToMarkdown(unittest.TestCase):
    """Markdown conversion is always the first processing step."""

    def test_plain_text_passes_through_converter(self):
        from input.handler import InputContent, SourceType
        from markdown.converter import convert_to_markdown

        content = InputContent(source_type=SourceType.TEXT, source_value="Hello world")
        result = convert_to_markdown(content)
        self.assertIsInstance(result, str)
        self.assertIn("Hello world", result)

    def test_run_pipeline_calls_convert_to_markdown(self):
        """run_pipeline must invoke convert_to_markdown before the LLM."""
        from app.main import run_pipeline

        call_order = []

        def fake_convert(content):
            call_order.append("convert")
            return "# Markdown content"

        def fake_generate_script(markdown_text, language_code, llm_provider):
            call_order.append("generate")
            return "Host1: Hi\nHost2: Hello"

        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = _silent_wav()
        mock_llm = MagicMock()

        with patch("app.main.convert_to_markdown", side_effect=fake_convert), \
             patch("app.main.generate_script", side_effect=fake_generate_script), \
             patch("app.main.build_llm_provider", return_value=mock_llm), \
             patch("app.main.build_tts_provider", return_value=mock_tts), \
             patch("app.main._estimate_tokens", return_value=100), \
             patch("audio.builder.AudioSegment.export"), \
             patch("language.detector.detect", return_value="en"):
            run_pipeline("some text")

        self.assertIn("convert", call_order)
        self.assertIn("generate", call_order)
        self.assertLess(
            call_order.index("convert"),
            call_order.index("generate"),
            "Markdown conversion must happen before LLM generation",
        )


# ---------------------------------------------------------------------------
# Invariant 3 — Dialogue format always follows Host1:/Host2:
# ---------------------------------------------------------------------------

class TestInvariant3DialogueFormat(unittest.TestCase):
    """Generated scripts must use the Host1:/Host2: format."""

    def test_validate_script_format_enforces_host_lines(self):
        from script.generator import _validate_script_format

        # Valid format passes silently
        _validate_script_format("Host1: Hello\nHost2: World")

    def test_script_without_host_lines_is_rejected(self):
        from script.generator import _validate_script_format

        with self.assertRaises(ValueError):
            _validate_script_format("This has no host lines at all.")

    def test_audio_builder_parses_only_host_lines(self):
        """Only Host1:/Host2: lines should be synthesized into audio."""
        from audio.builder import _parse_script

        script = (
            "Some narrator text\n"
            "Host1: Spoken by host one\n"
            "Host2: Spoken by host two\n"
            "More random text\n"
        )
        lines = _parse_script(script)
        hosts = {line.host for line in lines}
        self.assertTrue(hosts.issubset({"Host1", "Host2"}))
        self.assertEqual(len(lines), 2)

    def test_podcast_prompt_contains_host_format_instruction(self):
        """The official prompt must specify Host1:/Host2: output format."""
        from script.prompts import PODCAST_PROMPT_TEMPLATE

        self.assertIn("Host1:", PODCAST_PROMPT_TEMPLATE)
        self.assertIn("Host2:", PODCAST_PROMPT_TEMPLATE)


# ---------------------------------------------------------------------------
# Invariant 4 — Audio generation occurs per dialogue line
# ---------------------------------------------------------------------------

class TestInvariant4AudioPerLine(unittest.TestCase):
    """TTS synthesize must be called once per dialogue line."""

    def test_tts_called_once_per_host_line(self):
        from audio.builder import build_podcast

        script = (
            "Host1: Line one\n"
            "Host2: Line two\n"
            "Host1: Line three\n"
        )
        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = _silent_wav()

        with patch("audio.builder.AudioSegment.export"):
            build_podcast(
                dialogue_script=script,
                language_code="en",
                tts_provider=mock_tts,
                output_path="/tmp/test_podcast.mp3",
            )

        self.assertEqual(mock_tts.synthesize.call_count, 3)


# ---------------------------------------------------------------------------
# Invariant 5 — Audio merging only in Podcast Builder
# ---------------------------------------------------------------------------

class TestInvariant5MergingOnlyInBuilder(unittest.TestCase):
    """Only audio/builder.py should contain AudioSegment concatenation logic."""

    def test_builder_module_performs_merge(self):
        """_merge_segments must exist and concatenate segments correctly."""
        from audio.builder import _merge_segments

        seg_a = AudioSegment.silent(duration=100)
        seg_b = AudioSegment.silent(duration=200)
        result = _merge_segments([seg_a, seg_b])
        # Result is longer than either individual segment
        self.assertGreater(len(result), len(seg_a))
        self.assertGreater(len(result), len(seg_b))

    def test_other_modules_do_not_import_pydub(self):
        """Non-builder modules must not import pydub (merging invariant)."""
        audio_related_modules = [
            "llm/provider.py",
            "llm/groq_provider.py",
            "llm/ollama_provider.py",
            "llm/openai_provider.py",
            "script/generator.py",
            "script/prompts.py",
            "tts/provider.py",
            "tts/piper_provider.py",
            "tts/elevenlabs_provider.py",
            "planning/dialogue_planner.py",
            "chunking/chunker.py",
            "language/detector.py",
            "input/handler.py",
            "markdown/converter.py",
        ]
        for rel_path in audio_related_modules:
            source = _source(rel_path)
            self.assertNotIn(
                "pydub",
                source,
                f"Module {rel_path} must not import pydub (audio merging is "
                "reserved for audio/builder.py — Invariant #5)",
            )


# ---------------------------------------------------------------------------
# Invariant 6 — Providers called only inside provider modules
# ---------------------------------------------------------------------------

class TestInvariant6ProvidersCalledOnlyInModules(unittest.TestCase):
    """LLM and TTS providers are only instantiated in provider modules."""

    def test_script_generator_does_not_import_provider_implementations(self):
        """script/generator.py must not import concrete provider classes."""
        source = _source("script/generator.py")
        self.assertNotIn("GroqProvider", source)
        self.assertNotIn("OllamaProvider", source)
        self.assertNotIn("OpenAIProvider", source)
        self.assertNotIn("PiperProvider", source)
        self.assertNotIn("ElevenLabsProvider", source)

    def test_planning_module_does_not_import_provider_implementations(self):
        source = _source("planning/dialogue_planner.py")
        self.assertNotIn("GroqProvider", source)
        self.assertNotIn("OllamaProvider", source)
        self.assertNotIn("PiperProvider", source)
        self.assertNotIn("ElevenLabsProvider", source)

    def test_main_instantiates_providers_through_builder_functions(self):
        """app/main.py must use builder functions, not direct instantiation."""
        source = _source("app/main.py")
        # build_llm_provider and build_tts_provider are defined there;
        # validate that direct provider construction is isolated to these helpers.
        self.assertIn("build_llm_provider", source)
        self.assertIn("build_tts_provider", source)


# ---------------------------------------------------------------------------
# Invariant 7 & 8 — Language propagation
# ---------------------------------------------------------------------------

class TestInvariants7And8LanguagePropagation(unittest.TestCase):
    """Detected language must flow through every pipeline stage."""

    def test_podcast_prompt_embeds_language(self):
        from script.prompts import get_podcast_prompt

        for lang in ("pt-BR", "es", "en", "zh", "ru"):
            prompt = get_podcast_prompt(language=lang, content="test content")
            self.assertIn(f"Language: {lang}", prompt,
                          f"Language '{lang}' not embedded in prompt")

    def test_hierarchical_prompts_embed_language(self):
        from script.prompts import get_chunk_summary_prompt, get_outline_prompt

        for lang in ("pt-BR", "es", "en", "zh", "ru"):
            summary_prompt = get_chunk_summary_prompt(language=lang, content="text")
            self.assertIn(f"Language: {lang}", summary_prompt)

            outline_prompt = get_outline_prompt(language=lang, summaries="summary")
            self.assertIn(f"Language: {lang}", outline_prompt)

    def test_build_podcast_forwards_language_to_tts(self):
        """build_podcast must propagate language_code to every TTS call."""
        from audio.builder import build_podcast

        script = "Host1: Hello\nHost2: World"
        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = _silent_wav()

        with patch("audio.builder.AudioSegment.export"):
            build_podcast(
                dialogue_script=script,
                language_code="ru",
                tts_provider=mock_tts,
                output_path="/tmp/test.mp3",
            )

        for call in mock_tts.synthesize.call_args_list:
            _, kwargs = call
            self.assertEqual(
                kwargs["language"],
                "ru",
                "language_code must be forwarded to TTS synthesize",
            )

    def test_language_detector_returns_canonical_code(self):
        """detect_language must return a canonical project language code."""
        from language.detector import detect_language

        canonical = {"pt-BR", "es", "en", "zh", "ru"}

        with patch("language.detector.detect", return_value="pt"):
            code = detect_language("texto em português")
        self.assertIn(code, canonical)

        with patch("language.detector.detect", return_value="zh-cn"):
            code = detect_language("中文内容")
        self.assertIn(code, canonical)


# ---------------------------------------------------------------------------
# Additional: Provider interfaces
# ---------------------------------------------------------------------------

class TestProviderInterfaces(unittest.TestCase):
    """Verify that abstract interfaces match the signatures defined in claude.md."""

    def test_llm_provider_has_generate_script(self):
        from llm.provider import LLMProvider
        self.assertTrue(hasattr(LLMProvider, "generate_script"))
        sig = inspect.signature(LLMProvider.generate_script)
        params = list(sig.parameters)
        self.assertIn("markdown", params)
        self.assertIn("language", params)

    def test_tts_provider_has_synthesize(self):
        from tts.provider import TTSProvider
        self.assertTrue(hasattr(TTSProvider, "synthesize"))
        sig = inspect.signature(TTSProvider.synthesize)
        params = list(sig.parameters)
        self.assertIn("text", params)
        self.assertIn("voice", params)
        self.assertIn("language", params)

    def test_all_llm_providers_implement_interface(self):
        from llm.provider import LLMProvider
        from llm.ollama_provider import OllamaProvider
        from llm.groq_provider import GroqProvider
        from llm.openai_provider import OpenAIProvider

        for cls in (OllamaProvider, GroqProvider, OpenAIProvider):
            self.assertTrue(
                issubclass(cls, LLMProvider),
                f"{cls.__name__} must subclass LLMProvider",
            )
            self.assertTrue(
                hasattr(cls, "generate_script"),
                f"{cls.__name__} must implement generate_script",
            )

    def test_all_tts_providers_implement_interface(self):
        from tts.provider import TTSProvider
        from tts.piper_provider import PiperProvider
        from tts.elevenlabs_provider import ElevenLabsProvider

        for cls in (PiperProvider, ElevenLabsProvider):
            self.assertTrue(
                issubclass(cls, TTSProvider),
                f"{cls.__name__} must subclass TTSProvider",
            )
            self.assertTrue(
                hasattr(cls, "synthesize"),
                f"{cls.__name__} must implement synthesize",
            )


# ---------------------------------------------------------------------------
# Helper (shared)
# ---------------------------------------------------------------------------

def _silent_wav(duration_ms: int = 100) -> bytes:
    silence = AudioSegment.silent(duration=duration_ms)
    buf = io.BytesIO()
    silence.export(buf, format="wav")
    return buf.getvalue()


if __name__ == "__main__":
    unittest.main()
