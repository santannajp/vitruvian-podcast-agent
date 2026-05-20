"""
tts/provider.py — Abstract TTS provider interface.

All TTS implementations must subclass TTSProvider and implement
the synthesize method. Providers must never be called outside
their own modules (Architecture Invariant #6).
"""

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract base class for all Text-to-Speech provider implementations."""

    @abstractmethod
    def synthesize(self, text: str, voice: str, language: str) -> bytes:
        """
        Synthesize speech from text and return raw audio bytes.

        Args:
            text:     The dialogue text to synthesize.
            voice:    Voice identifier. Typically "voice_a" (Host1) or "voice_b" (Host2).
            language: Canonical language code (e.g. "pt-BR", "en").

        Returns:
            Raw audio data as bytes (WAV or MP3 depending on the provider).
        """
