"""
language/voices.py — Canonical voice and model mapping per language.

Provides the single source of truth for which TTS voices/models to use
for each supported language. Consumed by PiperProvider and ElevenLabsProvider.

Supported language codes: pt-BR, es, en, zh, ru
"""

import config

# ---------------------------------------------------------------------------
# Piper TTS — model paths per language (host1, host2)
# ---------------------------------------------------------------------------

_PIPER_MODELS_BY_LANGUAGE: dict[str, tuple[str, str]] = {
    "pt-BR": (config.PIPER_MODEL_HOST1, config.PIPER_MODEL_HOST2),
    "en":    (config.PIPER_MODEL_EN_HOST1, config.PIPER_MODEL_EN_HOST2),
    "es":    (config.PIPER_MODEL_ES_HOST1, config.PIPER_MODEL_ES_HOST2),
    "zh":    (config.PIPER_MODEL_ZH_HOST1, config.PIPER_MODEL_ZH_HOST2),
    "ru":    (config.PIPER_MODEL_RU_HOST1, config.PIPER_MODEL_RU_HOST2),
}

# Fallback language when the detected language is not in the map
_PIPER_FALLBACK_LANGUAGE = "en"


def get_piper_model(language: str, voice: str) -> str:
    """
    Return the Piper .onnx model path for the given language and voice.

    Looks up the language in the model table. Falls back to English if
    the language is not explicitly mapped.

    Args:
        language: Canonical language code (e.g. "pt-BR", "es", "zh").
        voice:    Voice identifier — "voice_a" (Host1) or "voice_b" (Host2).

    Returns:
        Path to the .onnx model file.

    Raises:
        ValueError: If the voice identifier is not "voice_a" or "voice_b".
    """
    if voice not in ("voice_a", "voice_b"):
        raise ValueError(
            f"Unknown voice '{voice}'. Supported voices: 'voice_a', 'voice_b'."
        )

    models = _PIPER_MODELS_BY_LANGUAGE.get(
        language,
        _PIPER_MODELS_BY_LANGUAGE[_PIPER_FALLBACK_LANGUAGE],
    )
    return models[0] if voice == "voice_a" else models[1]


# ---------------------------------------------------------------------------
# ElevenLabs — voice IDs per language (host1, host2)
# ---------------------------------------------------------------------------

# Pre-made ElevenLabs voices available on all accounts (multilingual v2 compatible).
# Used as ultimate fallback when no voice IDs are configured.
_ELEVENLABS_DEFAULT_HOST1 = "21m00Tcm4TlvDq8ikWAM"  # Rachel
_ELEVENLABS_DEFAULT_HOST2 = "pNInz6obpgDQGcFmaJgB"  # Adam


def _build_elevenlabs_map() -> dict[str, tuple[str, str]]:
    """Build the ElevenLabs voice-ID map from config at call time.

    When a config value is empty the pre-made default voice is substituted,
    so the pipeline works out-of-the-box without any .env configuration.
    """
    def _h1(val: str) -> str:
        return val or _ELEVENLABS_DEFAULT_HOST1

    def _h2(val: str) -> str:
        return val or _ELEVENLABS_DEFAULT_HOST2

    return {
        "pt-BR": (_h1(config.ELEVENLABS_VOICE_HOST1),    _h2(config.ELEVENLABS_VOICE_HOST2)),
        "en":    (_h1(config.ELEVENLABS_VOICE_EN_HOST1),  _h2(config.ELEVENLABS_VOICE_EN_HOST2)),
        "es":    (_h1(config.ELEVENLABS_VOICE_ES_HOST1),  _h2(config.ELEVENLABS_VOICE_ES_HOST2)),
        "zh":    (_h1(config.ELEVENLABS_VOICE_ZH_HOST1),  _h2(config.ELEVENLABS_VOICE_ZH_HOST2)),
        "ru":    (_h1(config.ELEVENLABS_VOICE_RU_HOST1),  _h2(config.ELEVENLABS_VOICE_RU_HOST2)),
    }


# Fallback: use pt-BR (default) voices when language-specific IDs are absent
_ELEVENLABS_FALLBACK_LANGUAGE = "pt-BR"


def get_elevenlabs_voice_id(language: str, voice: str) -> str:
    """
    Return the ElevenLabs voice ID for the given language and voice.

    Attempts a language-specific lookup first. If the resolved ID is empty
    (not configured), falls back to the default pt-BR voice IDs.

    Args:
        language: Canonical language code (e.g. "en", "ru").
        voice:    Voice identifier — "voice_a" (Host1) or "voice_b" (Host2).

    Returns:
        ElevenLabs voice ID string.

    Raises:
        ValueError: If the voice identifier is invalid or no voice ID
                    could be resolved (neither language-specific nor default).
    """
    if voice not in ("voice_a", "voice_b"):
        raise ValueError(
            f"Unknown voice '{voice}'. Supported voices: 'voice_a', 'voice_b'."
        )

    mapping = _build_elevenlabs_map()

    def _pick(ids: tuple[str, str]) -> str:
        return ids[0] if voice == "voice_a" else ids[1]

    # Try language-specific IDs first
    if language in mapping:
        voice_id = _pick(mapping[language])
        if voice_id:
            return voice_id

    # Fall back to default language
    fallback_ids = mapping.get(_ELEVENLABS_FALLBACK_LANGUAGE, ("", ""))
    voice_id = _pick(fallback_ids)
    if voice_id:
        return voice_id

    raise ValueError(
        f"No ElevenLabs voice ID configured for language '{language}', voice '{voice}'. "
        "Set ELEVENLABS_VOICE_HOST1 / ELEVENLABS_VOICE_HOST2 (and optionally "
        "ELEVENLABS_VOICE_<LANG>_HOST1/HOST2) in your .env file."
    )
