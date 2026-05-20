"""
script/generator.py — Podcast script generator.

Orchestrates dialogue generation in two modes:

  Simple pipeline (Phase 1):
    1. Retrieves the official prompt via script/prompts.py
    2. Calls the LLM provider
    3. Cleans and validates the output
    4. Returns the formatted dialogue script

  Hierarchical pipeline (Phase 2, for long documents):
    1. Summarises each Markdown chunk (via planning.dialogue_planner)
    2. Generates an episode outline from the summaries
    3. Generates the final dialogue using outline + summaries

This module does not contain any prompt strings. All prompts
live exclusively in script/prompts.py.
"""

from __future__ import annotations

import re
from typing import List

from chunking.chunker import Chunk
from llm.provider import LLMProvider
import planning.dialogue_planner as planner
from script.prompts import get_hierarchical_dialogue_prompt

# Matches a line that begins a Host1/Host2 turn, tolerating:
#   - leading invisible unicode (BOM, directional markers, ZWNBSP…)
#   - markdown bold markers (**Host1:** or *Host1:*)
#   - optional whitespace around the colon
_HOST_LINE_RE = re.compile(
    r"^[\s\u200b\u200c\u200d\u2060\u2068\u2069\ufeff]*"
    r"\*{0,2}Host[12]\*{0,2}\s*:\s*\S",
    re.MULTILINE,
)

# Matches an opening or closing markdown code fence line (``` or ~~~)
_CODE_FENCE_RE = re.compile(r"^[ \t]*(?:```|~~~)\w*[ \t]*$", re.MULTILINE)


def generate_script(
    markdown_text: str,
    language_code: str,
    llm_provider: LLMProvider,
) -> str:
    """
    Generate a podcast dialogue script from Markdown content.

    Args:
        markdown_text:  Markdown source content from the converter stage.
        language_code:  Canonical language code (e.g. "pt-BR", "en").
        llm_provider:   A concrete LLMProvider instance to call.

    Returns:
        A dialogue script string in the format:
            Host1: ...
            Host2: ...
            Host1: ...
            Host2: ...

    Raises:
        ValueError: If the generated script is empty or malformed.
        RuntimeError: Propagated from the LLM provider on API failures.
    """
    raw = llm_provider.generate_script(
        markdown=markdown_text,
        language=language_code,
    )

    script = _clean_llm_output(raw)

    if not script:
        raise ValueError("LLM returned an empty script.")

    _validate_script_format(script)

    return script


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _clean_llm_output(raw: str) -> str:
    """
    Normalise raw LLM output into a clean Host1/Host2 dialogue script.

    Handles common LLM output artefacts:
    - Markdown code fences (``` / ~~~)
    - Prose preamble before the first Host line ("Here is the dialogue:…")
    - Invisible unicode control/directional characters at line starts
    - Markdown bold markers around host names (**Host1:** → Host1:)
    - Extra whitespace around the colon (Host1 : text → Host1: text)

    Args:
        raw: Raw string returned by the LLM provider.

    Returns:
        Cleaned dialogue string, or empty string if nothing parseable is found.
    """
    text = raw.strip()

    # 1. Remove markdown code fences
    text = _CODE_FENCE_RE.sub("", text).strip()

    # 2. Drop any prose preamble — keep only from the first Host line onward
    match = _HOST_LINE_RE.search(text)
    if match:
        text = text[match.start():]

    # 3. Normalise each line
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        # Strip leading invisible unicode characters
        line = line.lstrip(
            "\u200b\u200c\u200d\u2060\u2068\u2069\ufeff\u00a0\u00ad"
        )
        # Remove markdown bold/italic around the host label
        line = re.sub(r"\*{1,2}(Host[12])\*{1,2}\s*:", r"\1:", line)
        # Normalise optional spaces around the colon
        line = re.sub(r"(Host[12])\s*:\s*", r"\1: ", line)
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _validate_script_format(script: str) -> None:
    """
    Validate that the script contains at least one Host1/Host2 dialogue line.

    Args:
        script: Cleaned dialogue string.

    Raises:
        ValueError: If no Host1/Host2 lines are found.
    """
    lines = [line.strip() for line in script.splitlines() if line.strip()]
    host_lines = [
        line for line in lines
        if line.startswith("Host1:") or line.startswith("Host2:")
    ]

    if not host_lines:
        raise ValueError(
            "Generated script does not contain any Host1:/Host2: lines. "
            f"Raw output (first 200 chars): {script[:200]!r}"
        )


# ---------------------------------------------------------------------------
# Hierarchical pipeline (Phase 2)
# ---------------------------------------------------------------------------

def generate_script_hierarchical(
    chunks: List[Chunk],
    llm_provider: LLMProvider,
    language_code: str,
) -> str:
    """Generate a podcast dialogue script using the hierarchical pipeline.

    This three-stage process is designed for long documents:
        Stage 1 — Summarise each chunk independently.
        Stage 2 — Build an episode outline from the summaries.
        Stage 3 — Generate the final dialogue from outline + summaries.

    Args:
        chunks:        List of Chunk objects from chunking.chunker.chunk_markdown().
        llm_provider:  A concrete LLMProvider instance.
        language_code: Canonical language code (e.g. "pt-BR", "en").

    Returns:
        A dialogue script string in the Host1:/Host2: format.

    Raises:
        ValueError:   If chunks is empty, or any stage produces empty output.
        RuntimeError: Propagated from the LLM provider on API failures.
    """
    if not chunks:
        raise ValueError("chunks list must not be empty.")

    # Stage 1 — Summarise each chunk
    summaries: List[str] = [
        planner.summarize_chunk(chunk, llm_provider, language_code)
        for chunk in chunks
    ]

    # Stage 2 — Generate episode outline
    outline: str = planner.generate_outline(summaries, llm_provider, language_code)

    # Stage 3 — Generate final dialogue
    combined_summaries = "\n\n".join(
        f"[Section {i + 1}]\n{s}" for i, s in enumerate(summaries)
    )
    prompt = get_hierarchical_dialogue_prompt(
        language=language_code,
        outline=outline,
        summaries=combined_summaries,
    )
    raw = llm_provider.generate_script(markdown=prompt, language=language_code)
    script = _clean_llm_output(raw)

    if not script:
        raise ValueError("LLM returned an empty script in the hierarchical pipeline.")

    _validate_script_format(script)

    return script
