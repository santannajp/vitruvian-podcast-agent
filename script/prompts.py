"""
script/prompts.py — Official podcast prompt definitions.

Prompts are stored here and never embedded inside generation functions.
All prompts must conform to the format defined in claude.md.

Phase 1 prompts:
    PODCAST_PROMPT_TEMPLATE         — Direct dialogue generation from Markdown.

Phase 2 prompts (hierarchical pipeline):
    CHUNK_SUMMARY_PROMPT_TEMPLATE   — Summarise a single Markdown chunk.
    OUTLINE_PROMPT_TEMPLATE         — Generate episode outline from summaries.
    HIERARCHICAL_DIALOGUE_PROMPT_TEMPLATE — Final dialogue from outline + summaries.
"""


# ---------------------------------------------------------------------------
# Official podcast generation prompt (as defined in claude.md)
# ---------------------------------------------------------------------------

PODCAST_PROMPT_TEMPLATE = """\
You are generating a podcast conversation between two hosts.

Your task is to transform the provided Markdown content into a natural dialogue.

Language: {language}

Rules:

- Two hosts: Host1 and Host2
- Conversation should feel natural and engaging
- Hosts explain concepts clearly
- Host2 may ask questions
- Avoid long monologues
- Keep dialogue balanced
- Maintain factual accuracy
- IMPORTANT: Focus exclusively on the article's substantive content — its ideas,\
 arguments, data, and conclusions. Do NOT mention, discuss, or reference the website,\
 newsletter, publication name, subscription prompts, author bios, social sharing\
 elements, comments sections, navigation menus, or any other website chrome. If such\
 elements appear in the content, ignore them completely.

Output format:

Host1: ...
Host2: ...
Host1: ...
Host2: ...

Content:
{content}
"""


def get_podcast_prompt(language: str, content: str) -> str:
    """
    Build the official podcast generation prompt.

    Args:
        language: Canonical language code (e.g. "pt-BR", "en").
        content:  Markdown content to transform into dialogue.

    Returns:
        Fully formatted prompt string ready to be sent to the LLM.
    """
    return PODCAST_PROMPT_TEMPLATE.format(language=language, content=content)


# ---------------------------------------------------------------------------
# Phase 2 — Hierarchical pipeline prompts
# ---------------------------------------------------------------------------

CHUNK_SUMMARY_PROMPT_TEMPLATE = """\
Summarise the following content section concisely.

Language: {language}

Rules:
- Write 3 to 5 sentences.
- Preserve the key ideas and any named entities.
- Do NOT generate dialogue.
- Ignore any website chrome: subscription prompts, navigation, sharing buttons,\
 author bios, footer content, or anything unrelated to the article's subject matter.

Content:
{content}
"""


def get_chunk_summary_prompt(language: str, content: str) -> str:
    """Build the chunk summary prompt.

    Args:
        language: Canonical language code (e.g. "pt-BR", "en").
        content:  Markdown text of a single chunk.

    Returns:
        Formatted prompt string.
    """
    return CHUNK_SUMMARY_PROMPT_TEMPLATE.format(language=language, content=content)


OUTLINE_PROMPT_TEMPLATE = """\
You are planning a podcast episode from the following content summaries.

Language: {language}

Create a structured discussion outline.

Rules:
- Use numbered sections (1. Introduction, 2. ..., N. Conclusion).
- Each section should have a short title and one-sentence description.
- Aim for 5 to 8 sections.
- Ensure a logical flow from introduction to conclusion.
- Base the outline exclusively on the article's substantive content.\
 Disregard any references to the publication, newsletter, or website.

Content summaries:
{summaries}
"""


def get_outline_prompt(language: str, summaries: str) -> str:
    """Build the episode outline prompt from combined chunk summaries.

    Args:
        language:  Canonical language code.
        summaries: All chunk summaries joined into a single text block.

    Returns:
        Formatted prompt string.
    """
    return OUTLINE_PROMPT_TEMPLATE.format(language=language, summaries=summaries)


HIERARCHICAL_DIALOGUE_PROMPT_TEMPLATE = """\
You are generating a podcast conversation between two hosts.

Language: {language}

Use the episode outline and the content summaries below to write a natural dialogue.

Rules:

- Two hosts: Host1 and Host2
- Follow the structure of the outline
- Conversation should feel natural and engaging
- Hosts explain concepts clearly
- Host2 may ask questions
- Avoid long monologues
- Keep dialogue balanced
- Maintain factual accuracy
- IMPORTANT: Focus exclusively on the article's substantive content — its ideas,\
 arguments, data, and conclusions. Do NOT mention, discuss, or reference the website,\
 newsletter, publication name, subscription prompts, author bios, social sharing\
 elements, or any other website chrome. If such elements appear in the summaries,\
 ignore them completely.

Output format:

Host1: ...
Host2: ...
Host1: ...
Host2: ...

Episode outline:
{outline}

Content summaries:
{summaries}
"""


def get_hierarchical_dialogue_prompt(language: str, outline: str, summaries: str) -> str:
    """Build the hierarchical dialogue generation prompt.

    Args:
        language:  Canonical language code.
        outline:   Episode outline generated by get_outline_prompt().
        summaries: All chunk summaries joined into a single text block.

    Returns:
        Formatted prompt string.
    """
    return HIERARCHICAL_DIALOGUE_PROMPT_TEMPLATE.format(
        language=language,
        outline=outline,
        summaries=summaries,
    )
