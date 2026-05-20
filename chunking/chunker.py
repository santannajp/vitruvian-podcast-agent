"""
chunking/chunker.py — Markdown content chunker.

Divides large Markdown documents into smaller segments (chunks),
respecting section headings and semantic boundaries.

Each chunk stays within a configurable token limit, as required by claude.md
(recommended: 1000–2000 tokens per chunk).

Output type: List[Chunk]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """Represents a single content chunk from a Markdown document.

    Attributes:
        index:       Zero-based position in the chunk sequence.
        heading:     The heading that introduces this chunk (may be empty).
        content:     The raw Markdown text of this chunk.
        token_count: Estimated token count for LLM budget purposes.
    """
    index: int
    heading: str
    content: str
    token_count: int = field(init=False)

    def __post_init__(self) -> None:
        self.token_count = _estimate_tokens(self.content)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_markdown(text: str, max_tokens: int = 1500) -> List[Chunk]:
    """Divide a Markdown document into semantically coherent chunks.

    Strategy:
    1. Split the document on Markdown headings (h1, h2, h3).
    2. If a section exceeds *max_tokens*, further split by paragraphs.
    3. Return a list of Chunk objects in document order.

    Args:
        text:       Full Markdown content to split.
        max_tokens: Maximum estimated token count per chunk.

    Returns:
        Ordered list of Chunk objects. Returns an empty list for empty input.
    """
    if not text or not text.strip():
        return []

    sections = _split_by_headings(text)
    chunks: List[Chunk] = []

    for heading, content in sections:
        content = content.strip()
        if not content:
            continue

        if _estimate_tokens(content) <= max_tokens:
            chunks.append(Chunk(index=len(chunks), heading=heading, content=content))
        else:
            # Section is too large — split by paragraphs
            sub_chunks = _split_by_paragraphs(content, max_tokens)
            for part in sub_chunks:
                chunks.append(Chunk(index=len(chunks), heading=heading, content=part))

    return chunks


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

# Regex that matches Markdown h1/h2/h3 headings
_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def _split_by_headings(text: str) -> List[tuple[str, str]]:
    """Split Markdown text into (heading, body) pairs at h1/h2/h3 boundaries.

    Any content before the first heading is grouped under an empty heading.

    Args:
        text: Full Markdown text.

    Returns:
        List of (heading_text, body_text) tuples.
    """
    sections: List[tuple[str, str]] = []
    last_end = 0
    last_heading = ""

    for match in _HEADING_RE.finditer(text):
        # Capture the body before this heading
        body = text[last_end:match.start()]
        if body.strip() or last_heading:
            sections.append((last_heading, body))

        last_heading = match.group(2).strip()
        last_end = match.end()

    # Capture trailing content after the last heading
    trailing = text[last_end:]
    sections.append((last_heading, trailing))

    return sections


def _split_by_paragraphs(text: str, max_tokens: int) -> List[str]:
    """Split a text block into paragraph-based chunks within *max_tokens*.

    Args:
        text:       Text to split (assumed to exceed max_tokens).
        max_tokens: Token budget per resulting chunk.

    Returns:
        List of text strings, each within the token budget.
    """
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current_parts: List[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = _estimate_tokens(para)
        if current_tokens + para_tokens > max_tokens and current_parts:
            chunks.append("\n\n".join(current_parts))
            current_parts = []
            current_tokens = 0
        current_parts.append(para)
        current_tokens += para_tokens

    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return chunks if chunks else [text]


def _estimate_tokens(text: str) -> int:
    """Estimate the number of tokens in a text string.

    Uses a word-count heuristic (no external dependencies):
        token_count ≈ word_count

    This is intentionally conservative; the real token count
    (BPE-based) is typically 1.2–1.5× the word count.

    Args:
        text: Input string.

    Returns:
        Estimated token count.
    """
    return len(text.split())
