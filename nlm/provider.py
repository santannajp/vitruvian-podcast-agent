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

        print("      [NLM] Connecting to NotebookLM...")
        async with await NotebookLMClient.from_storage() as client:
            print("      [NLM] Creating temporary notebook...")
            nb = await client.notebooks.create("Vitruvian-Audio-Temp")
            print(f"      [NLM] Notebook created: {nb.id}")
            try:
                await self._add_source(client, nb.id, content, markdown_text)

                # Verify sources were actually added before generating
                sources = await client.sources.list(nb.id)
                if not sources:
                    raise RuntimeError(
                        "NotebookLM accepted the source but no sources appear in the notebook. "
                        "The content may be too short, empty, or in an unsupported format."
                    )
                print(f"      [NLM] Verified: {len(sources)} source(s) in notebook")

                await self._generate_and_download(
                    client, nb.id, language_code, output_path
                )
            finally:
                try:
                    print("      [NLM] Cleaning up temporary notebook...")
                    await client.notebooks.delete(nb.id)
                except Exception:
                    # Cleanup failure is non-fatal.
                    pass

        return output_path

    async def _add_source(self, client, notebook_id: str, content: InputContent, markdown_text: str) -> None:
        """Add the appropriate source type to the notebook."""
        if content.source_type == SourceType.URL:
            # Pass the URL directly — NotebookLM fetches the full article.
            print(f"      [NLM] Adding URL source: {content.source_value}")
            await client.sources.add_url(notebook_id, content.source_value, wait=True)
            print("      [NLM] URL source added successfully")
        else:
            # For text and file inputs, send the pre-converted Markdown.
            text_preview = markdown_text[:80].replace('\n', ' ')
            print(f"      [NLM] Adding text source ({len(markdown_text)} chars): {text_preview}...")
            await client.sources.add_text(
                notebook_id,
                title="Content",
                content=markdown_text,
                wait=True,
            )
            print("      [NLM] Text source added successfully")

    async def _generate_and_download(
        self,
        client,
        notebook_id: str,
        language_code: str,
        output_path: str,
    ) -> None:
        """Trigger audio generation, wait for completion, and download."""
        import asyncio as _asyncio
        instructions: Optional[str] = config.NOTEBOOKLM_INSTRUCTIONS or None

        nlm_lang = _map_language(language_code)
        fmt = _audio_format()
        length = _audio_length()
        print(f"      [NLM] Requesting audio generation (lang={nlm_lang}, format={fmt}, length={length})...")

        status = await client.artifacts.generate_audio(
            notebook_id,
            language=nlm_lang,
            audio_format=fmt,
            audio_length=length,
            instructions=instructions,
        )
        print(f"      [NLM] Generation task submitted: {status.task_id}")
        print(f"      [NLM] Waiting for completion (timeout={config.NOTEBOOKLM_WAIT_TIMEOUT}s)...")

        # Poll with progress feedback instead of silent wait
        import time as _time
        start = _time.monotonic()
        poll_interval = 5.0
        max_interval = 15.0

        while True:
            poll_result = await client.artifacts.poll_status(notebook_id, status.task_id)
            elapsed = _time.monotonic() - start

            if poll_result.is_complete:
                print(f"      [NLM] ✅ Audio generation complete! ({elapsed:.0f}s)")
                break

            if poll_result.is_failed:
                error_msg = getattr(poll_result, 'error', None) or 'Unknown error'
                raise RuntimeError(
                    f"NotebookLM audio generation failed: {error_msg}"
                )

            if poll_result.status == "not_found":
                if elapsed > 30:
                    raise RuntimeError(
                        "NotebookLM removed the generation task. This may indicate "
                        "a daily quota limit was exceeded, or the content was rejected. "
                        "Try again later or with different content."
                    )

            if elapsed > config.NOTEBOOKLM_WAIT_TIMEOUT:
                raise TimeoutError(
                    f"NotebookLM audio generation timed out after {elapsed:.0f}s "
                    f"(status: {poll_result.status}). The content may be too long "
                    f"or the service may be overloaded. Try again later or use "
                    f"a shorter input."
                )

            print(f"      [NLM] ⏳ Status: {poll_result.status} ({elapsed:.0f}s elapsed)...")
            await _asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, max_interval)

        # On Windows, os.rename() fails if the destination already exists.
        # The Streamlit app pre-creates the temp file, so we remove it first.
        import os as _os
        if _os.path.exists(output_path):
            _os.remove(output_path)

        print("      [NLM] Downloading audio file...")
        await client.artifacts.download_audio(notebook_id, output_path)
        print(f"      [NLM] ✅ Audio saved to {output_path}")
