"""
tests/test_audio_builder.py — Unit tests for audio/builder.py
"""

import unittest
from unittest.mock import MagicMock, patch
import io

from pydub import AudioSegment

from audio.builder import (
    build_podcast,
    _parse_script,
    _synthesize_segments,
    _merge_segments,
    DialogueLine,
    PAUSE_BETWEEN_SPEAKERS_MS,
)
from tts.provider import TTSProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _silent_wav(duration_ms: int = 100) -> bytes:
    """Generate a silent WAV bytes object for mocking TTS output."""
    silence = AudioSegment.silent(duration=duration_ms)
    buf = io.BytesIO()
    silence.export(buf, format="wav")
    return buf.getvalue()


def _make_mock_tts(wav_bytes: bytes | None = None) -> TTSProvider:
    """Create a mock TTSProvider that returns silent WAV bytes."""
    if wav_bytes is None:
        wav_bytes = _silent_wav()
    mock = MagicMock(spec=TTSProvider)
    mock.synthesize.return_value = wav_bytes
    return mock


# ---------------------------------------------------------------------------
# Tests: _parse_script
# ---------------------------------------------------------------------------

class TestParseScript(unittest.TestCase):

    def test_parses_two_host_lines(self):
        script = "Host1: Hello!\nHost2: Hi there!"
        lines = _parse_script(script)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].host, "Host1")
        self.assertEqual(lines[0].text, "Hello!")
        self.assertEqual(lines[1].host, "Host2")
        self.assertEqual(lines[1].text, "Hi there!")

    def test_assigns_correct_voices(self):
        script = "Host1: Line one\nHost2: Line two"
        lines = _parse_script(script)
        self.assertEqual(lines[0].voice, "voice_a")
        self.assertEqual(lines[1].voice, "voice_b")

    def test_skips_blank_lines(self):
        script = "\nHost1: Hello!\n\nHost2: World!\n"
        lines = _parse_script(script)
        self.assertEqual(len(lines), 2)

    def test_skips_lines_without_host_prefix(self):
        script = "Host1: Valid\nSome random text\nHost2: Also valid"
        lines = _parse_script(script)
        self.assertEqual(len(lines), 2)

    def test_skips_host_line_with_empty_text(self):
        script = "Host1:\nHost2: Something"
        lines = _parse_script(script)
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].host, "Host2")

    def test_empty_script_returns_empty_list(self):
        lines = _parse_script("")
        self.assertEqual(lines, [])

    def test_returns_dialogue_line_instances(self):
        script = "Host1: Test"
        lines = _parse_script(script)
        self.assertIsInstance(lines[0], DialogueLine)


# ---------------------------------------------------------------------------
# Tests: _synthesize_segments
# ---------------------------------------------------------------------------

class TestSynthesizeSegments(unittest.TestCase):

    def test_returns_audio_segment_per_line(self):
        lines = [
            DialogueLine(host="Host1", text="Hello", voice="voice_a"),
            DialogueLine(host="Host2", text="Hi", voice="voice_b"),
        ]
        mock_tts = _make_mock_tts()
        segments = _synthesize_segments(lines, language_code="en", tts_provider=mock_tts)
        self.assertEqual(len(segments), 2)
        for seg in segments:
            self.assertIsInstance(seg, AudioSegment)

    def test_tts_called_with_correct_args(self):
        lines = [DialogueLine(host="Host1", text="Hello world", voice="voice_a")]
        mock_tts = _make_mock_tts()
        _synthesize_segments(lines, language_code="pt-BR", tts_provider=mock_tts)
        mock_tts.synthesize.assert_called_once_with(
            text="Hello world",
            voice="voice_a",
            language="pt-BR",
        )


# ---------------------------------------------------------------------------
# Tests: _merge_segments
# ---------------------------------------------------------------------------

class TestMergeSegments(unittest.TestCase):

    def test_single_segment_returns_unchanged(self):
        silence = AudioSegment.silent(duration=200)
        result = _merge_segments([silence])
        # Duration should match the input (no pauses added for a single segment)
        self.assertEqual(len(result), len(silence))

    def test_two_segments_include_pause(self):
        seg_a = AudioSegment.silent(duration=200)
        seg_b = AudioSegment.silent(duration=300)
        result = _merge_segments([seg_a, seg_b])
        expected_ms = len(seg_a) + PAUSE_BETWEEN_SPEAKERS_MS + len(seg_b)
        self.assertEqual(len(result), expected_ms)


# ---------------------------------------------------------------------------
# Tests: build_podcast (integration, TTS mocked)
# ---------------------------------------------------------------------------

class TestBuildPodcast(unittest.TestCase):

    VALID_SCRIPT = "Host1: Welcome!\nHost2: Thanks for having me."

    def test_build_podcast_returns_output_path(self):
        mock_tts = _make_mock_tts()
        with patch("audio.builder.config.OUTPUT_PATH", "podcast.mp3"), \
             patch.object(AudioSegment, "export") as mock_export:
            result = build_podcast(
                dialogue_script=self.VALID_SCRIPT,
                language_code="en",
                tts_provider=mock_tts,
            )
        self.assertEqual(result, "podcast.mp3")

    def test_build_podcast_uses_custom_output_path(self):
        mock_tts = _make_mock_tts()
        with patch.object(AudioSegment, "export") as mock_export:
            result = build_podcast(
                dialogue_script=self.VALID_SCRIPT,
                language_code="en",
                tts_provider=mock_tts,
                output_path="/tmp/my_podcast.mp3",
            )
        self.assertEqual(result, "/tmp/my_podcast.mp3")

    def test_empty_script_raises_value_error(self):
        mock_tts = _make_mock_tts()
        with self.assertRaises(ValueError) as ctx:
            build_podcast(
                dialogue_script="No host lines here.",
                language_code="en",
                tts_provider=mock_tts,
                output_path="/tmp/out.mp3",
            )
        self.assertIn("no parseable", str(ctx.exception))

    def test_tts_called_for_each_dialogue_line(self):
        mock_tts = _make_mock_tts()
        with patch.object(AudioSegment, "export"):
            build_podcast(
                dialogue_script=self.VALID_SCRIPT,
                language_code="en",
                tts_provider=mock_tts,
                output_path="/tmp/out.mp3",
            )
        self.assertEqual(mock_tts.synthesize.call_count, 2)

    def test_export_called_with_mp3_format(self):
        mock_tts = _make_mock_tts()
        with patch.object(AudioSegment, "export") as mock_export:
            build_podcast(
                dialogue_script=self.VALID_SCRIPT,
                language_code="en",
                tts_provider=mock_tts,
                output_path="/tmp/out.mp3",
            )
        mock_export.assert_called_once_with("/tmp/out.mp3", format="mp3")


if __name__ == "__main__":
    unittest.main()
