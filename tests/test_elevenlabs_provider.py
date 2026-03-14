"""
tests/test_elevenlabs_provider.py — Unit tests for tts/elevenlabs_provider.py
"""

import unittest
from unittest.mock import patch, MagicMock


class TestResolveVoiceId(unittest.TestCase):
    """
    Tests for voice ID resolution.

    _resolve_voice_id() was moved to language/voices.get_elevenlabs_voice_id()
    in Phase 4. Full coverage lives in test_language_voice_mapping.py.
    These tests verify the same behaviour through the new public API.
    """

    def test_voice_a_resolves_to_host1(self):
        from language.voices import get_elevenlabs_voice_id
        with patch("config.ELEVENLABS_VOICE_HOST1", "voice-id-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "voice-id-h2"):
            result = get_elevenlabs_voice_id("pt-BR", "voice_a")
        self.assertEqual(result, "voice-id-h1")

    def test_voice_b_resolves_to_host2(self):
        from language.voices import get_elevenlabs_voice_id
        with patch("config.ELEVENLABS_VOICE_HOST1", "voice-id-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "voice-id-h2"):
            result = get_elevenlabs_voice_id("pt-BR", "voice_b")
        self.assertEqual(result, "voice-id-h2")

    def test_unknown_voice_raises_value_error(self):
        from language.voices import get_elevenlabs_voice_id
        with patch("config.ELEVENLABS_VOICE_HOST1", "voice-id-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "voice-id-h2"):
            with self.assertRaises(ValueError) as ctx:
                get_elevenlabs_voice_id("pt-BR", "voice_z")
        self.assertIn("voice_z", str(ctx.exception))

    def test_missing_voice_id_raises_value_error(self):
        from language.voices import get_elevenlabs_voice_id
        # All voice IDs unconfigured → should raise ValueError
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
                get_elevenlabs_voice_id("en", "voice_a")


class TestElevenLabsProvider(unittest.TestCase):

    def _make_provider(self, api_key="el_key"):
        mock_el_cls = MagicMock()
        mock_client = MagicMock()
        mock_el_cls.return_value = mock_client

        mock_el_module = MagicMock()
        mock_el_module.client.ElevenLabs = mock_el_cls

        with patch.dict("sys.modules", {
            "elevenlabs": mock_el_module,
            "elevenlabs.client": mock_el_module.client,
        }), \
             patch("config.ELEVENLABS_API_KEY", api_key), \
             patch("config.ELEVENLABS_MODEL", "eleven_turbo_v2"), \
             patch("config.ELEVENLABS_VOICE_HOST1", "v-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "v-h2"):
            import importlib
            import tts.elevenlabs_provider as mod
            importlib.reload(mod)
            provider = mod.ElevenLabsProvider()
        provider._client = mock_client
        return provider, mock_client

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_provider_raises_import_error_when_elevenlabs_missing(self):
        with patch.dict("sys.modules", {
            "elevenlabs": None,
            "elevenlabs.client": None,
        }), \
             patch("config.ELEVENLABS_API_KEY", "key"), \
             patch("config.ELEVENLABS_MODEL", "model"), \
             patch("config.ELEVENLABS_VOICE_HOST1", "v1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "v2"):
            import importlib
            import tts.elevenlabs_provider as mod
            importlib.reload(mod)
            with self.assertRaises(ImportError):
                mod.ElevenLabsProvider()

    def test_provider_raises_value_error_when_api_key_missing(self):
        mock_el_module = MagicMock()
        with patch.dict("sys.modules", {
            "elevenlabs": mock_el_module,
            "elevenlabs.client": mock_el_module.client,
        }), \
             patch("config.ELEVENLABS_API_KEY", ""), \
             patch("config.ELEVENLABS_MODEL", "model"), \
             patch("config.ELEVENLABS_VOICE_HOST1", "v1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "v2"):
            import importlib
            import tts.elevenlabs_provider as mod
            importlib.reload(mod)
            with self.assertRaises(ValueError) as ctx:
                mod.ElevenLabsProvider()
        self.assertIn("ELEVENLABS_API_KEY", str(ctx.exception))

    # ------------------------------------------------------------------
    # Successful call
    # ------------------------------------------------------------------

    def test_synthesize_returns_audio_bytes(self):
        provider, mock_client = self._make_provider()
        fake_audio = b"MP3BYTES"
        mock_client.text_to_speech.convert.return_value = iter([fake_audio])

        with patch("config.ELEVENLABS_VOICE_HOST1", "v-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "v-h2"):
            import importlib
            import tts.elevenlabs_provider as mod
            importlib.reload(mod)
            provider2 = mod.ElevenLabsProvider.__new__(mod.ElevenLabsProvider)
            provider2._client = mock_client
            provider2.model = "eleven_turbo_v2"
            result = provider2.synthesize(text="Hello", voice="voice_a", language="en")

        self.assertEqual(result, fake_audio)

    def test_synthesize_unknown_voice_raises_value_error(self):
        provider, mock_client = self._make_provider()

        with patch("config.ELEVENLABS_VOICE_HOST1", "v-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "v-h2"):
            import importlib
            import tts.elevenlabs_provider as mod
            importlib.reload(mod)
            provider2 = mod.ElevenLabsProvider.__new__(mod.ElevenLabsProvider)
            provider2._client = mock_client
            provider2.model = "eleven_turbo_v2"
            with self.assertRaises(ValueError):
                provider2.synthesize(text="Hello", voice="voice_zzz", language="en")

    def test_synthesize_api_error_raises_runtime_error(self):
        provider, mock_client = self._make_provider()
        mock_client.text_to_speech.convert.side_effect = Exception("API down")

        with patch("config.ELEVENLABS_VOICE_HOST1", "v-h1"), \
             patch("config.ELEVENLABS_VOICE_HOST2", "v-h2"):
            import importlib
            import tts.elevenlabs_provider as mod
            importlib.reload(mod)
            provider2 = mod.ElevenLabsProvider.__new__(mod.ElevenLabsProvider)
            provider2._client = mock_client
            provider2.model = "eleven_turbo_v2"
            with self.assertRaises(RuntimeError) as ctx:
                provider2.synthesize(text="Hello", voice="voice_a", language="en")

        self.assertIn("ElevenLabs API error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
