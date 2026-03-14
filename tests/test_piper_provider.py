"""
tests/test_piper_provider.py — Unit tests for tts/piper_provider.py
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import subprocess


_FAKE_PIPER_MODELS = {
    "pt-BR": ("models/host1.onnx", "models/host2.onnx"),
    "en":    ("models/en1.onnx",   "models/en2.onnx"),
    "es":    ("models/es1.onnx",   "models/es2.onnx"),
    "zh":    ("models/zh1.onnx",   "models/zh2.onnx"),
    "ru":    ("models/ru1.onnx",   "models/ru2.onnx"),
}


class TestGetPiperModel(unittest.TestCase):
    """Tests for voice→model resolution via language.voices.get_piper_model.

    Patches _PIPER_MODELS_BY_LANGUAGE directly because the dict is built
    at module import time from config values.
    """

    def test_voice_a_resolves_to_host1_model(self):
        with patch("language.voices._PIPER_MODELS_BY_LANGUAGE", _FAKE_PIPER_MODELS):
            from language.voices import get_piper_model
            result = get_piper_model(language="pt-BR", voice="voice_a")
        self.assertEqual(result, "models/host1.onnx")

    def test_voice_b_resolves_to_host2_model(self):
        with patch("language.voices._PIPER_MODELS_BY_LANGUAGE", _FAKE_PIPER_MODELS):
            from language.voices import get_piper_model
            result = get_piper_model(language="pt-BR", voice="voice_b")
        self.assertEqual(result, "models/host2.onnx")

    def test_unknown_voice_raises_value_error(self):
        from language.voices import get_piper_model
        with self.assertRaises(ValueError) as ctx:
            get_piper_model(language="en", voice="voice_c")
        self.assertIn("voice_c", str(ctx.exception))


class TestPiperProviderSynthesize(unittest.TestCase):

    FAKE_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt "  # minimal fake WAV header

    def _make_provider(self):
        with patch("config.PIPER_EXECUTABLE", "piper"), \
             patch("config.PIPER_MODEL_HOST1", "models/host1.onnx"), \
             patch("config.PIPER_MODEL_HOST2", "models/host2.onnx"):
            import importlib
            import tts.piper_provider as mod
            importlib.reload(mod)
            return mod.PiperProvider()

    def test_synthesize_returns_wav_bytes(self):
        provider = self._make_provider()

        mock_proc_result = MagicMock()
        mock_proc_result.returncode = 0
        mock_proc_result.stderr = b""

        with patch("subprocess.run", return_value=mock_proc_result), \
             patch("builtins.open", mock_open(read_data=self.FAKE_WAV)), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            result = provider.synthesize(text="Hello world", voice="voice_a", language="en")

        self.assertEqual(result, self.FAKE_WAV)

    def test_synthesize_nonzero_exit_raises_runtime_error(self):
        provider = self._make_provider()

        mock_proc_result = MagicMock()
        mock_proc_result.returncode = 1
        mock_proc_result.stderr = b"Piper crashed"

        with patch("subprocess.run", return_value=mock_proc_result), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove"):
            with self.assertRaises(RuntimeError) as ctx:
                provider.synthesize(text="Hello", voice="voice_a", language="en")
        self.assertIn("Piper TTS failed", str(ctx.exception))

    def test_synthesize_unknown_voice_raises_value_error(self):
        provider = self._make_provider()

        with self.assertRaises(ValueError):
            provider.synthesize(text="Hello", voice="voice_zzz", language="en")

    def test_tmp_file_cleaned_up_on_success(self):
        provider = self._make_provider()

        mock_proc_result = MagicMock()
        mock_proc_result.returncode = 0
        mock_proc_result.stderr = b""

        remove_calls = []

        with patch("subprocess.run", return_value=mock_proc_result), \
             patch("builtins.open", mock_open(read_data=self.FAKE_WAV)), \
             patch("os.path.exists", return_value=True), \
             patch("os.remove", side_effect=lambda p: remove_calls.append(p)):
            provider.synthesize(text="Hello", voice="voice_b", language="en")

        self.assertTrue(len(remove_calls) > 0, "os.remove should be called on temp file")


if __name__ == "__main__":
    unittest.main()
