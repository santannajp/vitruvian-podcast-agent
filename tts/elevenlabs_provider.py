"""
tts/elevenlabs_provider.py — TTS provider via ElevenLabs API.

Uses the official elevenlabs Python SDK to synthesize speech.
Voice selection is language-aware: the correct voice ID is chosen based
on the detected language via language.voices.get_elevenlabs_voice_id().

API key, voice IDs and model are configured via config.py / .env.
"""

import config
from tts.provider import TTSProvider
from language.voices import get_elevenlabs_voice_id


class ElevenLabsProvider(TTSProvider):
    """TTS provider that calls the ElevenLabs API cloud service."""

    def __init__(self) -> None:
        # Lazy import so the library is only required when this provider is used.
        try:
            from elevenlabs.client import ElevenLabs  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "elevenlabs package is required for ElevenLabsProvider. "
                "Install it with: pip install elevenlabs"
            ) from exc

        api_key: str = config.ELEVENLABS_API_KEY
        if not api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is not set. "
                "Add it to your .env file or environment variables."
            )

        self.model: str = config.ELEVENLABS_MODEL
        self._client = ElevenLabs(api_key=api_key)

    def synthesize(self, text: str, voice: str, language: str) -> bytes:
        """
        Synthesize speech from text using ElevenLabs.

        Selects the appropriate voice ID for the given language. Falls back
        to the default pt-BR voice IDs when no language-specific voice is
        configured.

        Args:
            text:     The dialogue text to synthesize.
            voice:    Canonical voice name ("voice_a" for Host1, "voice_b" for Host2).
            language: Canonical language code (e.g. "pt-BR", "en", "es", "zh", "ru").
                      Used to select the correct language-specific voice.

        Returns:
            Raw MP3 audio bytes.

        Raises:
            ValueError: If the voice name is unknown or its ID is not configured.
            RuntimeError: If the ElevenLabs API call fails.
        """
        voice_id = get_elevenlabs_voice_id(language=language, voice=voice)
        return self._call_elevenlabs(text=text, voice_id=voice_id)

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _call_elevenlabs(self, text: str, voice_id: str) -> bytes:
        """
        Send a text-to-speech request to the ElevenLabs API.

        Args:
            text:     Text to synthesize.
            voice_id: ElevenLabs voice ID.

        Returns:
            Raw MP3 audio bytes.

        Raises:
            RuntimeError: On API error.
        """
        try:
            audio_generator = self._client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=self.model,
            )
            # The SDK returns a generator; consume it into bytes.
            return b"".join(audio_generator)
        except Exception as exc:
            raise RuntimeError(f"ElevenLabs API error: {exc}") from exc
