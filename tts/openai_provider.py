"""
tts/openai_provider.py — TTS provider via OpenAI Speech API.

Uses the openai Python SDK to synthesize speech.
Returns WAV bytes (response_format="wav") so the audio builder can process
them without format conversion, consistent with other providers.

Voice mapping (overridable via config / sidebar):
    voice_a (Host1) → config.OPENAI_TTS_VOICE_A  (default: "onyx"  — deep male)
    voice_b (Host2) → config.OPENAI_TTS_VOICE_B  (default: "nova"  — warm female)

Available voices: alloy, echo, fable, onyx, nova, shimmer, ash, ballad, coral, sage
Model:            config.OPENAI_TTS_MODEL          (default: "tts-1-hd")

API key is shared with the LLM provider via OPENAI_API_KEY.
"""

import config
from tts.provider import TTSProvider

# Voices are read from config at instantiation time so sidebar overrides take effect.
_VOICE_A_DEFAULT = "onyx"   # deep male — consistent in pt-BR
_VOICE_B_DEFAULT = "nova"   # warm female — consistent in pt-BR


class OpenAITTSProvider(TTSProvider):
    """TTS provider that calls the OpenAI Speech API."""

    def __init__(self) -> None:
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "openai package is required for OpenAITTSProvider. "
                "Install it with: pip install openai"
            ) from exc

        api_key: str = config.OPENAI_API_KEY
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. "
                "Add it to your .env file or set it in the sidebar."
            )

        self._client = OpenAI(api_key=api_key)
        self._model: str = config.OPENAI_TTS_MODEL
        self._voice_map: dict[str, str] = {
            "voice_a": config.OPENAI_TTS_VOICE_A,
            "voice_b": config.OPENAI_TTS_VOICE_B,
        }

    def synthesize(self, text: str, voice: str, language: str) -> bytes:
        """
        Synthesize speech using the OpenAI TTS API.

        Args:
            text:     The dialogue text to synthesize.
            voice:    Canonical voice name — "voice_a" (Host1) or "voice_b" (Host2).
            language: Language code (not used directly; OpenAI TTS is multilingual).

        Returns:
            Raw WAV audio bytes.

        Raises:
            ValueError: If the voice identifier is not recognised.
            RuntimeError: If the OpenAI API call fails.
        """
        openai_voice = self._voice_map.get(voice)
        if openai_voice is None:
            raise ValueError(
                f"Unknown voice '{voice}'. Expected 'voice_a' or 'voice_b'."
            )
        return self._call_openai(text=text, openai_voice=openai_voice)

    # ---------------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------------

    def _call_openai(self, text: str, openai_voice: str) -> bytes:
        """
        Send a speech synthesis request to the OpenAI API.

        Returns WAV bytes for compatibility with the audio builder.

        Args:
            text:         Text to synthesize.
            openai_voice: OpenAI voice name (e.g. "alloy", "nova").

        Returns:
            WAV bytes.

        Raises:
            RuntimeError: On API error.
        """
        try:
            response = self._client.audio.speech.create(
                model=self._model,
                voice=openai_voice,
                input=text,
                response_format="wav",
            )
            return response.content
        except Exception as exc:
            raise RuntimeError(f"OpenAI TTS API error: {exc}") from exc
