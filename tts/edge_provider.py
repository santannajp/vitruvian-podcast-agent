"""
tts/edge_provider.py — Microsoft Edge TTS provider.

Uses the free, key-less edge-tts library that streams synthesis from the
public Microsoft Edge read-aloud endpoint. Returns WAV bytes so the rest
of the pipeline does not need ffmpeg to load segments.

Voice mapping:
    voice_a (Host1) → config.EDGE_TTS_VOICE_A   (default: pt-BR Antonio — male)
    voice_b (Host2) → config.EDGE_TTS_VOICE_B   (default: pt-BR Francisca — female)

Per-language overrides are honored if the detected language matches one of the
known buckets (en, es, zh, ru). Anything else falls back to the configured
default voices.
"""

import asyncio
import io
import wave

import config
from tts.provider import TTSProvider


# Per-language voice tables — picked at synthesize() time from the
# detected language code.
_PER_LANGUAGE_VOICES: dict[str, dict[str, str]] = {
    "pt": {"voice_a": "pt-BR-AntonioNeural",   "voice_b": "pt-BR-FranciscaNeural"},
    "en": {"voice_a": "en-US-GuyNeural",       "voice_b": "en-US-JennyNeural"},
    "es": {"voice_a": "es-ES-AlvaroNeural",    "voice_b": "es-ES-ElviraNeural"},
    "zh": {"voice_a": "zh-CN-YunxiNeural",     "voice_b": "zh-CN-XiaoxiaoNeural"},
    "ru": {"voice_a": "ru-RU-DmitryNeural",    "voice_b": "ru-RU-SvetlanaNeural"},
}


class EdgeTTSProvider(TTSProvider):
    """TTS provider that calls Microsoft Edge's read-aloud endpoint."""

    def __init__(self) -> None:
        try:
            import edge_tts  # noqa: F401  — import-time availability check
        except ImportError as exc:
            raise ImportError(
                "edge-tts package is required for EdgeTTSProvider. "
                "Install it with: pip install edge-tts"
            ) from exc

        try:
            import miniaudio  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "miniaudio package is required to decode Edge TTS output. "
                "Install it with: pip install miniaudio"
            ) from exc

        self._default_voice_a: str = config.EDGE_TTS_VOICE_A
        self._default_voice_b: str = config.EDGE_TTS_VOICE_B

    def synthesize(self, text: str, voice: str, language: str) -> bytes:
        """
        Synthesize *text* with Edge TTS and return WAV bytes.

        Args:
            text:     The text to synthesize.
            voice:    Canonical voice — "voice_a" (Host1) or "voice_b" (Host2).
            language: Language code (e.g. "pt-BR", "en") used to pick a
                      per-language voice when the user has not configured one.

        Raises:
            ValueError: Unknown voice identifier.
            RuntimeError: Edge TTS request failed.
        """
        edge_voice = self._resolve_voice(voice, language)
        mp3_bytes = asyncio.run(self._stream_mp3(text, edge_voice))
        return _mp3_to_wav(mp3_bytes)

    # ------------------------------------------------------------------
    # Voice resolution
    # ------------------------------------------------------------------

    def _resolve_voice(self, voice: str, language: str) -> str:
        if voice not in ("voice_a", "voice_b"):
            raise ValueError(
                f"Unknown voice '{voice}'. Expected 'voice_a' or 'voice_b'."
            )

        lang_prefix = (language or "").lower().split("-")[0]
        if lang_prefix in _PER_LANGUAGE_VOICES:
            return _PER_LANGUAGE_VOICES[lang_prefix][voice]

        return self._default_voice_a if voice == "voice_a" else self._default_voice_b

    # ------------------------------------------------------------------
    # Network call
    # ------------------------------------------------------------------

    async def _stream_mp3(self, text: str, edge_voice: str) -> bytes:
        """
        Stream MP3 audio from the Edge TTS endpoint, retrying on transient
        websocket / socket-read timeouts (the public endpoint occasionally
        drops mid-stream for long texts).
        """
        import edge_tts  # local import keeps the module importable without the dep

        max_attempts = 3
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                communicate = edge_tts.Communicate(text, edge_voice)
                chunks: list[bytes] = []
                async for piece in communicate.stream():
                    if piece.get("type") == "audio":
                        chunks.append(piece["data"])

                if not chunks:
                    raise RuntimeError(
                        f"Edge TTS returned no audio for voice '{edge_voice}'. "
                        "The voice name may be invalid or the service may be unreachable."
                    )

                return b"".join(chunks)
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts:
                    backoff = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    print(
                        f"      [Edge TTS] attempt {attempt}/{max_attempts} failed "
                        f"({exc}); retrying in {backoff}s…"
                    )
                    await asyncio.sleep(backoff)

        raise RuntimeError(
            f"Edge TTS request failed after {max_attempts} attempts: {last_exc}"
        ) from last_exc


# ---------------------------------------------------------------------------
# MP3 → WAV (pure-Python, no ffmpeg)
# ---------------------------------------------------------------------------

def _mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """Decode MP3 → PCM with miniaudio, repackage as 16-bit WAV bytes."""
    import miniaudio  # noqa: PLC0415

    decoded = miniaudio.decode(
        mp3_bytes,
        output_format=miniaudio.SampleFormat.SIGNED16,
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(decoded.nchannels)
        wav.setsampwidth(decoded.sample_width)
        wav.setframerate(decoded.sample_rate)
        wav.writeframes(bytes(decoded.samples))
    return buf.getvalue()
