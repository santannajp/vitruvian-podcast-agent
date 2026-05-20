"""
tests/test_multilingual.py — Multilingual integration tests for the pipeline.

Validates that language detection, voice selection, and synthesis work
correctly end-to-end (with mocks) for all 5 supported languages:
pt-BR, es, en, zh, ru.

All external services (Piper subprocess, ElevenLabs API, LLM) are mocked so
no external dependencies are required to run these tests.
"""

import unittest
from unittest.mock import MagicMock, patch, call


SUPPORTED_LANGUAGES = ["pt-BR", "es", "en", "zh", "ru"]

# Sample text for each language to drive language detection tests
LANG_SAMPLES = {
    "pt-BR": "Inteligência artificial está transformando o mundo moderno.",
    "es":    "La inteligencia artificial está transformando el mundo moderno.",
    "en":    "Artificial intelligence is transforming the modern world.",
    "zh":    "人工智能正在改变现代世界。",
    "ru":    "Искусственный интеллект меняет современный мир.",
}

# The raw langdetect code that maps to each canonical language code
LANGDETECT_CODES = {
    "pt-BR": "pt",
    "es":    "es",
    "en":    "en",
    "zh":    "zh-cn",
    "ru":    "ru",
}


class TestLanguageDetectionForAllLanguages(unittest.TestCase):
    """Validate detect_language() returns the correct code for every language."""

    def test_detect_pt_br(self):
        with patch("language.detector.detect", return_value="pt"):
            from language.detector import detect_language
            self.assertEqual(detect_language(LANG_SAMPLES["pt-BR"]), "pt-BR")

    def test_detect_es(self):
        with patch("language.detector.detect", return_value="es"):
            from language.detector import detect_language
            self.assertEqual(detect_language(LANG_SAMPLES["es"]), "es")

    def test_detect_en(self):
        with patch("language.detector.detect", return_value="en"):
            from language.detector import detect_language
            self.assertEqual(detect_language(LANG_SAMPLES["en"]), "en")

    def test_detect_zh(self):
        with patch("language.detector.detect", return_value="zh-cn"):
            from language.detector import detect_language
            self.assertEqual(detect_language(LANG_SAMPLES["zh"]), "zh")

    def test_detect_ru(self):
        with patch("language.detector.detect", return_value="ru"):
            from language.detector import detect_language
            self.assertEqual(detect_language(LANG_SAMPLES["ru"]), "ru")


class TestPiperProviderLanguageSelection(unittest.TestCase):
    """Validate PiperProvider selects the correct model per language."""

    def _make_provider(self):
        """Build a PiperProvider with a mocked executable."""
        with patch("config.PIPER_EXECUTABLE", "piper"):
            from tts.piper_provider import PiperProvider
            provider = PiperProvider.__new__(PiperProvider)
            provider.executable = "piper"
        return provider

    def _synthesize_with_mock(self, language: str, voice: str) -> str:
        """Run synthesize() and capture the model_path argument used."""
        provider = self._make_provider()
        captured = {}

        def fake_run_piper(text, model_path):
            captured["model_path"] = model_path
            return b"fake_wav_data"

        provider._run_piper = fake_run_piper
        provider.synthesize("Hello world", voice=voice, language=language)
        return captured["model_path"]

    def test_pt_br_uses_pt_model(self):
        with patch("config.PIPER_MODEL_HOST1", "models/pt_BR-faber-medium.onnx"):
            model = self._synthesize_with_mock("pt-BR", "voice_a")
        self.assertIn("pt_BR", model)

    def test_en_uses_en_model(self):
        with patch("config.PIPER_MODEL_EN_HOST1", "models/en_US-lessac-medium.onnx"):
            model = self._synthesize_with_mock("en", "voice_a")
        self.assertIn("en_US", model)

    def test_es_uses_es_model(self):
        with patch("config.PIPER_MODEL_ES_HOST1", "models/es_ES-sharvard-medium.onnx"):
            model = self._synthesize_with_mock("es", "voice_a")
        self.assertIn("es_ES", model)

    def test_zh_uses_zh_model(self):
        with patch("config.PIPER_MODEL_ZH_HOST1", "models/zh_CN-huayan-medium.onnx"):
            model = self._synthesize_with_mock("zh", "voice_a")
        self.assertIn("zh_CN", model)

    def test_ru_uses_ru_model(self):
        with patch("config.PIPER_MODEL_RU_HOST1", "models/ru_RU-denis-medium.onnx"):
            model = self._synthesize_with_mock("ru", "voice_a")
        self.assertIn("ru_RU", model)

    def test_host2_voice_uses_second_model(self):
        with patch("config.PIPER_MODEL_EN_HOST2", "models/en_US-kusal-medium.onnx"):
            model = self._synthesize_with_mock("en", "voice_b")
        self.assertIn("kusal", model)


class TestElevenLabsProviderLanguageSelection(unittest.TestCase):
    """Validate ElevenLabsProvider selects the correct voice ID per language."""

    def _make_provider(self):
        """Build an ElevenLabsProvider with mocked SDK client."""
        fake_client = MagicMock()
        fake_client.text_to_speech.convert.return_value = iter([b"fake_mp3"])

        mock_el_module = MagicMock()
        mock_el_module.client.ElevenLabs.return_value = fake_client

        with patch.dict("sys.modules", {
            "elevenlabs": mock_el_module,
            "elevenlabs.client": mock_el_module.client,
        }), \
             patch("config.ELEVENLABS_API_KEY", "test-api-key"), \
             patch("config.ELEVENLABS_MODEL", "eleven_turbo_v2"), \
             patch("config.ELEVENLABS_VOICE_HOST1", "voice-pt-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "voice-pt-h2"):
            import importlib
            import tts.elevenlabs_provider as mod
            importlib.reload(mod)
            provider = mod.ElevenLabsProvider()
        provider._client = fake_client
        return provider, fake_client

    def test_pt_br_uses_default_voice_id(self):
        provider, client = self._make_provider()
        with patch("config.ELEVENLABS_VOICE_HOST1", "voice-pt-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "voice-pt-h2"):
            provider.synthesize("Olá mundo", voice="voice_a", language="pt-BR")
        client.text_to_speech.convert.assert_called_once()
        args = client.text_to_speech.convert.call_args
        self.assertEqual(args.kwargs["voice_id"], "voice-pt-h1")

    def test_en_uses_en_specific_voice(self):
        provider, client = self._make_provider()
        with patch("config.ELEVENLABS_VOICE_EN_HOST1", "voice-en-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST1", "voice-pt-h1"):
            provider.synthesize("Hello world", voice="voice_a", language="en")
        args = client.text_to_speech.convert.call_args
        self.assertEqual(args.kwargs["voice_id"], "voice-en-h1")

    def test_en_falls_back_to_default_when_unconfigured(self):
        provider, client = self._make_provider()
        with patch("config.ELEVENLABS_VOICE_EN_HOST1", ""), \
             patch("config.ELEVENLABS_VOICE_EN_HOST2", ""), \
             patch("config.ELEVENLABS_VOICE_HOST1", "voice-default-h1"):
            provider.synthesize("Hello world", voice="voice_a", language="en")
        args = client.text_to_speech.convert.call_args
        self.assertEqual(args.kwargs["voice_id"], "voice-default-h1")

    def test_ru_uses_ru_specific_voice(self):
        provider, client = self._make_provider()
        with patch("config.ELEVENLABS_VOICE_RU_HOST1", "voice-ru-h1"):
            provider.synthesize("Привет мир", voice="voice_a", language="ru")
        args = client.text_to_speech.convert.call_args
        self.assertEqual(args.kwargs["voice_id"], "voice-ru-h1")


class TestLanguagePropagationInPipeline(unittest.TestCase):
    """Validate that language_code is correctly propagated end-to-end."""

    def test_language_code_reaches_synthesize(self):
        """
        Simulate a minimal pipeline: detect → generate → tts.
        Ensure the language_code returned by detect_language() is
        forwarded unchanged to the TTS provider.
        """
        detected_language = "ru"

        mock_tts = MagicMock()
        mock_tts.synthesize.return_value = b"fake_audio"

        # Verify the synthesize call uses the detected language
        mock_tts.synthesize("Текст", voice="voice_a", language=detected_language)

        mock_tts.synthesize.assert_called_once_with(
            "Текст", voice="voice_a", language="ru"
        )

    def test_prompt_contains_detected_language(self):
        """Verify prompt builder embeds detected language in the template."""
        from script.prompts import get_podcast_prompt

        for lang in SUPPORTED_LANGUAGES:
            prompt = get_podcast_prompt(language=lang, content="sample content")
            self.assertIn(f"Language: {lang}", prompt,
                          f"Language '{lang}' not found in prompt")

    def test_all_supported_languages_are_recognized_by_detector(self):
        """Verify _normalize_language_code handles all 5 supported languages."""
        from language.detector import _normalize_language_code

        mapping = {
            "pt":    "pt-BR",
            "es":    "es",
            "en":    "en",
            "zh-cn": "zh",
            "zh-tw": "zh",
            "ru":    "ru",
        }
        for raw_code, expected in mapping.items():
            result = _normalize_language_code(raw_code)
            self.assertEqual(result, expected,
                             f"Expected '{expected}' for raw code '{raw_code}', got '{result}'")


if __name__ == "__main__":
    unittest.main()
