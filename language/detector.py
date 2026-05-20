"""
language/detector.py — Language detection for Markdown content.

Detects the language of the processed Markdown and maps it to one of
the supported language codes: pt-BR, es, en, zh, ru.
"""

from langdetect import detect, LangDetectException

# Supported language codes (as defined in claude.md)
SUPPORTED_LANGUAGES = {"pt", "pt-BR", "es", "en", "zh", "zh-cn", "zh-tw", "ru"}

# Map langdetect codes → project canonical codes
_LANG_MAP: dict[str, str] = {
    "pt": "pt-BR",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "zh": "zh",
}


def detect_language(markdown_text: str) -> str:
    """
    Detect the language of the given Markdown text.

    Args:
        markdown_text: The Markdown content to analyse.

    Returns:
        A canonical language code string (e.g. "pt-BR", "en", "es", "zh", "ru").
        Falls back to "en" if detection fails or the language is unsupported.
    """
    if not markdown_text or not markdown_text.strip():
        return "en"

    try:
        raw_code = detect(markdown_text)
    except LangDetectException:
        return "en"

    return _normalize_language_code(raw_code)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _normalize_language_code(raw_code: str) -> str:
    """
    Map a raw langdetect code to the project's canonical language code.

    Args:
        raw_code: Language code returned by langdetect (e.g. "pt", "zh-cn").

    Returns:
        Canonical language code recognised by the pipeline.
    """
    normalized = raw_code.lower()

    if normalized in _LANG_MAP:
        return _LANG_MAP[normalized]

    if normalized in SUPPORTED_LANGUAGES:
        return normalized

    # Default to English for unsupported languages
    return "en"
