"""
nlm/provider.py — NotebookLM end-to-end podcast provider.

Uses the unofficial notebooklm-py library to generate audio overviews
directly from URLs or Markdown text, bypassing the LLM and TTS pipeline
stages entirely.

Invariant: this module is the only place where NotebookLMClient is called.
Notebook cleanup (delete) is always performed in a finally block.

Prerequisites:
    pip install "notebooklm-py[browser]"
    playwright install chromium
    notebooklm login
"""

import asyncio
from typing import Optional

import config
from input.handler import InputContent, SourceType


# ---------------------------------------------------------------------------
# Language code normalisation
# ---------------------------------------------------------------------------

# NotebookLM uses IETF language tags. Map internal codes to ones accepted by
# the generate_audio() API. Pass through anything not listed here unchanged.
_LANGUAGE_MAP: dict[str, str] = {
    "pt-BR": "pt-BR",
    "en":    "en-US",
    "es":    "es-ES",
    "zh":    "zh-CN",
    "ru":    "ru-RU",
}


def _map_language(language_code: str) -> str:
    """Return the NotebookLM-compatible language tag for *language_code*."""
    return _LANGUAGE_MAP.get(language_code, language_code)


# ---------------------------------------------------------------------------
# Audio format / length helpers
# ---------------------------------------------------------------------------

def _audio_format():
    """Return the notebooklm AudioFormat enum value from config."""
    from notebooklm.types import AudioFormat  # type: ignore[import]

    mapping = {
        "deep-dive": AudioFormat.DEEP_DIVE,
        "brief":     AudioFormat.BRIEF,
        "critique":  AudioFormat.CRITIQUE,
        "debate":    AudioFormat.DEBATE,
    }
    key = config.NOTEBOOKLM_AUDIO_FORMAT.lower()
    if key not in mapping:
        raise ValueError(
            f"Unknown NOTEBOOKLM_AUDIO_FORMAT '{config.NOTEBOOKLM_AUDIO_FORMAT}'. "
            "Valid options: 'deep-dive', 'brief', 'critique', 'debate'."
        )
    return mapping[key]


def _audio_length():
    """Return the notebooklm AudioLength enum value from config."""
    from notebooklm.types import AudioLength  # type: ignore[import]

    mapping = {
        "short":   AudioLength.SHORT,
        "default": AudioLength.DEFAULT,
        "long":    AudioLength.LONG,
    }
    key = config.NOTEBOOKLM_AUDIO_LENGTH.lower()
    if key not in mapping:
        raise ValueError(
            f"Unknown NOTEBOOKLM_AUDIO_LENGTH '{config.NOTEBOOKLM_AUDIO_LENGTH}'. "
            "Valid options: 'short', 'default', 'long'."
        )
    return mapping[key]


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class NotebookLMPodcastProvider:
    """Generate a podcast MP3 using Google NotebookLM.

    Wraps the async notebooklm-py client behind a synchronous interface so it
    integrates cleanly with the existing pipeline.
    """

    def generate(
        self,
        content: InputContent,
        language_code: str,
        markdown_text: str,
        output_path: str,
    ) -> str:
        """Generate a podcast from *content* and save it to *output_path*.

        Args:
            content: Validated input (URL, file, or text).
            language_code: Detected language code (e.g. "pt-BR", "en").
            markdown_text: Pre-converted Markdown (used for TEXT/FILE sources).
                           For URL sources this is used only for language
                           detection and is NOT sent to NotebookLM — the URL
                           itself is added as a source so the full article
                           content is preserved.
            output_path: Destination path for the generated MP3.

        Returns:
            The *output_path* string after the file has been written.

        Raises:
            RuntimeError: If audio generation or download fails.
        """
        return asyncio.run(
            self._async_generate(content, language_code, markdown_text, output_path)
        )

    # ------------------------------------------------------------------
    # Async implementation
    # ------------------------------------------------------------------

    async def _async_generate(
        self,
        content: InputContent,
        language_code: str,
        markdown_text: str,
        output_path: str,
    ) -> str:
        from notebooklm import NotebookLMClient  # type: ignore[import]

        async with await NotebookLMClient.from_storage() as client:
            nb = await client.notebooks.create("Vitruvian-Audio-Temp")
            try:
                await self._add_source(client, nb.id, content, markdown_text)
                await self._generate_and_download(
                    client, nb.id, language_code, output_path
                )
            finally:
                try:
                    await client.notebooks.delete(nb.id)
                except Exception:
                    # Cleanup failure is non-fatal.
                    pass

        return output_path

    async def _add_source(self, client, notebook_id: str, content: InputContent, markdown_text: str) -> None:
        """Add the appropriate source type to the notebook."""
        if content.source_type == SourceType.URL:
            # Pass the URL directly — NotebookLM fetches the full article.
            await client.sources.add_url(notebook_id, content.source_value, wait=True)
        else:
            # For text and file inputs, send the pre-converted Markdown.
            await client.sources.add_text(
                notebook_id,
                title="Content",
                content=markdown_text,
                wait=True,
            )

    async def _generate_and_download(
        self,
        client,
        notebook_id: str,
        language_code: str,
        output_path: str,
    ) -> None:
        """Trigger audio generation, wait for completion, and download."""
        instructions: Optional[str] = config.NOTEBOOKLM_INSTRUCTIONS or None

        status = await client.artifacts.generate_audio(
            notebook_id,
            language=_map_language(language_code),
            audio_format=_audio_format(),
            audio_length=_audio_length(),
            instructions=instructions,
        )

        await client.artifacts.wait_for_completion(
            notebook_id, status.task_id, timeout=config.NOTEBOOKLM_WAIT_TIMEOUT
        )

        # On Windows, os.rename() fails if the destination already exists.
        # The Streamlit app pre-creates the temp file, so we remove it first.
        import os as _os
        if _os.path.exists(output_path):
            _os.remove(output_path)

        await client.artifacts.download_audio(notebook_id, output_path)
