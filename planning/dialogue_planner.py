"""
planning/dialogue_planner.py — Dialogue planning module.

Orchestrates the two intermediate stages of the hierarchical pipeline:
    Stage 1 — Summarise each Markdown chunk independently.
    Stage 2 — Combine summaries into a structured episode outline.

These stages precede the final dialogue generation in script/generator.py.

Depends on:
    chunking.chunker.Chunk
    llm.provider.LLMProvider
    script.prompts (CHUNK_SUMMARY and OUTLINE templates)
"""

from __future__ import annotations

from typing import List

from chunking.chunker import Chunk
from llm.provider import LLMProvider
from script.prompts import get_chunk_summary_prompt, get_outline_prompt


# ---------------------------------------------------------------------------
# Stage 1 — Chunk Summarisation
# ---------------------------------------------------------------------------

def summarize_chunk(
    chunk: Chunk,
    llm_provider: LLMProvider,
    language: str,
) -> str:
    """Summarise a single Markdown chunk into a concise text block.

    Args:
        chunk:        A Chunk object produced by chunking.chunker.chunk_markdown().
        llm_provider: A concrete LLMProvider instance.
        language:     Canonical language code (e.g. "pt-BR", "en").

    Returns:
        Summary string for the chunk.

    Raises:
        ValueError:   If the LLM returns an empty summary.
        RuntimeError: Propagated from the LLM provider on API failures.
    """
    prompt = get_chunk_summary_prompt(language=language, content=chunk.content)
    summary = llm_provider.generate_script(markdown=prompt, language=language)
    summary = summary.strip()

    if not summary:
        raise ValueError(
            f"LLM returned an empty summary for chunk {chunk.index} "
            f"(heading: {chunk.heading!r})."
        )

    return summary


# ---------------------------------------------------------------------------
# Stage 2 — Outline Generation
# ---------------------------------------------------------------------------

def generate_outline(
    summaries: List[str],
    llm_provider: LLMProvider,
    language: str,
) -> str:
    """Generate a structured episode outline from chunk summaries.

    Args:
        summaries:    Ordered list of chunk summary strings.
        llm_provider: A concrete LLMProvider instance.
        language:     Canonical language code.

    Returns:
        Formatted episode outline string.

    Raises:
        ValueError:   If summaries list is empty or outline is empty.
        RuntimeError: Propagated from the LLM provider on API failures.
    """
    if not summaries:
        raise ValueError("Cannot generate an outline from an empty summaries list.")

    combined_summaries = _join_summaries(summaries)
    prompt = get_outline_prompt(language=language, summaries=combined_summaries)
    outline = llm_provider.generate_script(markdown=prompt, language=language)
    outline = outline.strip()

    if not outline:
        raise ValueError("LLM returned an empty outline.")

    return outline


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _join_summaries(summaries: List[str]) -> str:
    """Join chunk summaries into a single numbered text block.

    Args:
        summaries: List of summary strings.

    Returns:
        Numbered summary block.
    """
    parts = [f"[Section {i + 1}]\n{s}" for i, s in enumerate(summaries)]
    return "\n\n".join(parts)
