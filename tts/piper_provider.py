"""
tts/piper_provider.py — Local TTS provider via Piper.

Synthesizes speech by calling the Piper TTS executable as a subprocess.
Model selection is language-aware: the correct .onnx model is chosen based
on the detected language via language.voices.get_piper_model().

Model paths and the executable path are configured via config.py / .env.

Piper models can be downloaded from:
https://github.com/rhasspy/piper/releases
"""

import subprocess
import tempfile
import os

import config
from tts.provider import TTSProvider
from language.voices import get_piper_model


class PiperProvider(TTSProvider):
    """TTS provider that uses the local Piper TTS executable."""

    def __init__(self) -> None:
        self.executable: str = config.PIPER_EXECUTABLE

    def synthesize(self, text: str, voice: str, language: str) -> bytes:
        """
        Synthesize speech using Piper TTS.

        Selects the appropriate .onnx model for the given language and voice.

        Args:
            text:     Text to synthesize.
            voice:    Voice identifier — "voice_a" (Host1) or "voice_b" (Host2).
            language: Canonical language code (e.g. "pt-BR", "en", "es", "zh", "ru").
                      Used to select the correct language-specific Piper model.

        Returns:
            WAV audio data as bytes.

        Raises:
            ValueError: If the voice identifier is not mapped to a model.
            RuntimeError: If Piper fails or is not installed.
        """
        model_path = get_piper_model(language=language, voice=voice)
        return self._run_piper(text=text, model_path=model_path)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _run_piper(self, text: str, model_path: str) -> bytes:
        """
        Invoke Piper as a subprocess and capture WAV output.

        Args:
            text:       Text input for synthesis.
            model_path: Path to the .onnx model file.

        Returns:
            WAV bytes from Piper stdout.

        Raises:
            RuntimeError: If Piper exits with a non-zero code.
        """
        with tempfile.NamedTemporaryFile(
            suffix=".wav", delete=False
        ) as tmp_file:
            tmp_path = tmp_file.name

        try:
            cmd = [
                self.executable,
                "--model", model_path,
                "--output_file", tmp_path,
            ]

            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=120,
            )

            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"Piper TTS failed (exit {result.returncode}): {stderr}"
                )

            with open(tmp_path, "rb") as f:
                return f.read()

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
