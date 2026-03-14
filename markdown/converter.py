"""
markdown/converter.py — Converts any InputContent to Markdown text.

Uses MarkItDown to handle URLs, PDFs, documents, and raw text.
Plain text inputs are passed through with minimal normalisation.

After conversion, a boilerplate-stripping pass removes common web-page chrome
(navigation, subscription CTAs, social sharing prompts, footer content) so the
LLM receives only the substantive article text.
"""

import re

from input.handler import InputContent, SourceType

# ---------------------------------------------------------------------------
# Boilerplate patterns — lines matching any of these are discarded.
# Patterns are case-insensitive and must match the *entire* stripped line
# (anchored with ^ and $) or a dominant portion of very short lines.
# ---------------------------------------------------------------------------
_BOILERPLATE_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    # Subscription / sign-up CTAs
    r"^subscribe.*$",
    r"^unsubscribe.*$",
    r"^sign up.*$",
    r"^get the (newsletter|latest|updates?).*$",
    r"^\d+\s*(subscriber|reader|member)s?.*$",

    # Social / sharing / engagement chrome
    r"^share(\s+this\s+(post|article|story))?$",
    r"^(copy\s+)?link$",
    r"^(leave\s+a?\s*)?comment(s)?$",
    r"^\d+\s*(like|comment|share|repost)s?$",
    r"^(like|repost|reply|restack)$",
    r"^(facebook|twitter|linkedin|instagram|tiktok|youtube|x\.com)$",

    # Navigation / page chrome
    r"^(home|about|archive|contact|search|menu|top|back\s+to\s+top)$",
    r"^(previous|next)\s+(post|article|issue)$",
    r"^\s*©\s*\d{4}.*$",  # copyright lines
    r"^all rights reserved.*$",
    r"^privacy\s+policy.*$",
    r"^terms\s+of\s+(use|service).*$",

    # Substack / newsletter-specific chrome
    r"^(read|view)\s+(in|on)\s+(browser|app|substack).*$",
    r"^powered\s+by\s+substack.*$",
    r"^manage\s+(your\s+)?subscription.*$",
    r"^\d+\s*hr\s+ago$",   # timestamps stripped
    r"^\d+\s*min(ute)?s?\s*(read|ago)$",
]]


def convert_to_markdown(content: InputContent) -> str:
    """
    Convert an InputContent into a Markdown string.

    Args:
        content: A validated InputContent instance from the input handler.

    Returns:
        A Markdown-formatted string ready for language detection and LLM processing.

    Raises:
        RuntimeError: If MarkItDown fails to convert the given input.
    """
    if content.source_type == SourceType.TEXT:
        return _normalize_text(content.source_value)

    raw = _convert_with_markitdown(content.source_value)
    return _strip_boilerplate(raw)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Lightly normalise plain text — strip leading/trailing whitespace per line."""
    lines = text.splitlines()
    normalized = "\n".join(line.rstrip() for line in lines)
    return normalized.strip()


def _strip_boilerplate(markdown: str) -> str:
    """
    Remove common web-page boilerplate lines from converted Markdown.

    Targets subscription CTAs, social sharing prompts, navigation items,
    and footer content that MarkItDown picks up from web pages.  Substantive
    content (paragraphs, headings, lists, code blocks) is preserved.

    Args:
        markdown: Raw Markdown string from MarkItDown.

    Returns:
        Cleaned Markdown with boilerplate lines removed.
    """
    cleaned: list[str] = []
    consecutive_blanks = 0

    for line in markdown.splitlines():
        stripped = line.strip()

        # Keep empty lines but collapse runs of more than 2
        if not stripped:
            consecutive_blanks += 1
            if consecutive_blanks <= 2:
                cleaned.append("")
            continue
        consecutive_blanks = 0

        # Discard lines that match any boilerplate pattern
        if any(pat.match(stripped) for pat in _BOILERPLATE_PATTERNS):
            continue

        cleaned.append(line)

    return "\n".join(cleaned).strip()


def _convert_with_markitdown(source: str) -> str:
    """
    Use MarkItDown to convert a URL or file path to Markdown.

    Args:
        source: URL or absolute file path.

    Returns:
        Markdown text extracted from the source.

    Raises:
        RuntimeError: On MarkItDown conversion failure.
    """
    try:
        from markitdown import MarkItDown
        md = MarkItDown()
        result = md.convert(source)
        return result.text_content
    except Exception as exc:
        raise RuntimeError(f"MarkItDown conversion failed for '{source}': {exc}") from exc
