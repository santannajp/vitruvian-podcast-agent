"""
tests/test_language_voice_mapping.py — Unit tests for language/voices.py

Validates that the correct Piper model paths and ElevenLabs voice IDs
are returned for each of the 5 supported languages (pt-BR, es, en, zh, ru).
"""

import unittest
from unittest.mock import patch, MagicMock


class TestGetPiperModel(unittest.TestCase):
    """Tests for language.voices.get_piper_model()."""

    def _call(self, language: str, voice: str) -> str:
        from language.voices import get_piper_model
        return get_piper_model(language=language, voice=voice)

    def test_pt_br_voice_a_returns_host1_model(self):
        with patch("config.PIPER_MODEL_HOST1", "models/pt_BR-faber-medium.onnx"):
            result = self._call("pt-BR", "voice_a")
        self.assertIn("pt_BR", result)

    def test_pt_br_voice_b_returns_host2_model(self):
        with patch("config.PIPER_MODEL_HOST2", "models/pt_BR-edresson-low.onnx"):
            result = self._call("pt-BR", "voice_b")
        self.assertIn("pt_BR", result)

    def test_en_voice_a_returns_en_host1_model(self):
        with patch("config.PIPER_MODEL_EN_HOST1", "models/en_US-lessac-medium.onnx"):
            result = self._call("en", "voice_a")
        self.assertIn("en_US", result)

    def test_en_voice_b_returns_en_host2_model(self):
        with patch("config.PIPER_MODEL_EN_HOST2", "models/en_US-kusal-medium.onnx"):
            result = self._call("en", "voice_b")
        self.assertIn("en_US", result)

    def test_es_voice_a_returns_es_model(self):
        with patch("config.PIPER_MODEL_ES_HOST1", "models/es_ES-sharvard-medium.onnx"):
            result = self._call("es", "voice_a")
        self.assertIn("es_ES", result)

    def test_zh_voice_a_returns_zh_model(self):
        with patch("config.PIPER_MODEL_ZH_HOST1", "models/zh_CN-huayan-medium.onnx"):
            result = self._call("zh", "voice_a")
        self.assertIn("zh_CN", result)

    def test_ru_voice_a_returns_ru_model(self):
        with patch("config.PIPER_MODEL_RU_HOST1", "models/ru_RU-denis-medium.onnx"):
            result = self._call("ru", "voice_a")
        self.assertIn("ru_RU", result)

    def test_ru_voice_b_returns_ru_host2_model(self):
        with patch("config.PIPER_MODEL_RU_HOST2", "models/ru_RU-irina-medium.onnx"):
            result = self._call("ru", "voice_b")
        self.assertIn("ru_RU", result)

    def test_unsupported_language_falls_back_to_en(self):
        with patch("config.PIPER_MODEL_EN_HOST1", "models/en_US-lessac-medium.onnx"):
            result = self._call("ja", "voice_a")
        self.assertIn("en_US", result)

    def test_invalid_voice_raises_value_error(self):
        with self.assertRaises(ValueError):
            self._call("en", "voice_c")


class TestGetElevenLabsVoiceId(unittest.TestCase):
    """Tests for language.voices.get_elevenlabs_voice_id()."""

    def _call(self, language: str, voice: str) -> str:
        from language.voices import get_elevenlabs_voice_id
        return get_elevenlabs_voice_id(language=language, voice=voice)

    def test_pt_br_voice_a_returns_host1(self):
        with patch("config.ELEVENLABS_VOICE_HOST1", "voice-id-pt-h1"):
            result = self._call("pt-BR", "voice_a")
        self.assertEqual(result, "voice-id-pt-h1")

    def test_pt_br_voice_b_returns_host2(self):
        with patch("config.ELEVENLABS_VOICE_HOST2", "voice-id-pt-h2"):
            result = self._call("pt-BR", "voice_b")
        self.assertEqual(result, "voice-id-pt-h2")

    def test_en_voice_a_returns_en_specific_id(self):
        with patch("config.ELEVENLABS_VOICE_EN_HOST1", "voice-id-en-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST1", "default-h1"):
            result = self._call("en", "voice_a")
        self.assertEqual(result, "voice-id-en-h1")

    def test_en_fallback_to_default_when_not_configured(self):
        with patch("config.ELEVENLABS_VOICE_EN_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_EN_HOST2", ""), \
             patch("config.ELEVENLABS_VOICE_HOST1", "default-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "default-h2"):
            result = self._call("en", "voice_a")
        self.assertEqual(result, "default-h1")

    def test_es_voice_b_specific_id(self):
        with patch("config.ELEVENLABS_VOICE_ES_HOST2", "voice-id-es-h2"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "default-h2"):
            result = self._call("es", "voice_b")
        self.assertEqual(result, "voice-id-es-h2")

    def test_zh_voice_a_fallback_to_default(self):
        with patch("config.ELEVENLABS_VOICE_ZH_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_ZH_HOST2", ""), \
             patch("config.ELEVENLABS_VOICE_HOST1", "default-h1"):
            result = self._call("zh", "voice_a")
        self.assertEqual(result, "default-h1")

    def test_ru_voice_a_uses_ru_specific_id(self):
        with patch("config.ELEVENLABS_VOICE_RU_HOST1", "voice-id-ru-h1"):
            result = self._call("ru", "voice_a")
        self.assertEqual(result, "voice-id-ru-h1")

    def test_no_voice_configured_raises_value_error(self):
        with patch("config.ELEVENLABS_VOICE_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_HOST2", ""), \
             patch("config.ELEVENLABS_VOICE_EN_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_EN_HOST2", ""), \
             patch("config.ELEVENLABS_VOICE_ES_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_ES_HOST2", ""), \
             patch("config.ELEVENLABS_VOICE_ZH_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_ZH_HOST2", ""), \
             patch("config.ELEVENLABS_VOICE_RU_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_RU_HOST2", ""):
            with self.assertRaises(ValueError):
                self._call("en", "voice_a")

    def test_invalid_voice_raises_value_error(self):
        with self.assertRaises(ValueError):
            self._call("en", "voice_c")


if __name__ == "__main__":
    unittest.main()
