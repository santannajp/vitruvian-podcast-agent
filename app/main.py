"""
app/main.py — Pipeline entry point.

Orchestrates the full Content → Podcast pipeline:
    Input → Markdown → Language Detection → (Chunking) → Script Generation → TTS → Podcast MP3

For short content the simple pipeline is used (Phase 1).
For long content (exceeding config.LONG_CONTENT_THRESHOLD tokens) the
hierarchical pipeline is used: chunk → summarise → outline → dialogue (Phase 2).

Usage:
    python app/main.py --text "Your content here"
    python app/main.py --file path/to/document.pdf
    python app/main.py --url https://example.com/article
"""

import argparse
import sys
import os

# ---------------------------------------------------------------------------
# Path setup — ensure project root is on sys.path when running from app/
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from nlm.bootstrap import bootstrap_storage_state

# Materialize NotebookLM session from secret if NOTEBOOKLM_STORAGE_STATE_B64
# is set. No-op otherwise — local development is unaffected.
bootstrap_storage_state()

from input.handler import handle_input
from markdown.converter import convert_to_markdown
from language.detector import detect_language
from chunking.chunker import chunk_markdown, _estimate_tokens
from script.generator import generate_script, generate_script_hierarchical
from audio.builder import build_podcast
from llm.provider import LLMProvider
from tts.provider import TTSProvider


def build_llm_provider() -> LLMProvider:
    """
    Instantiate and return the active LLM provider based on config.LLM_PROVIDER.

    Supported values: "ollama" (default), "groq", "openai".

    Returns:
        An LLMProvider instance.

    Raises:
        ValueError: If an unknown provider name is specified.
    """
    provider_name = config.LLM_PROVIDER.lower()
    if provider_name == "ollama":
        from llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    if provider_name == "groq":
        from llm.groq_provider import GroqProvider
        return GroqProvider()
    if provider_name == "openai":
        from llm.openai_provider import OpenAIProvider
        return OpenAIProvider()
    raise ValueError(
        f"Unknown LLM_PROVIDER '{config.LLM_PROVIDER}'. "
        "Valid options: 'ollama', 'groq', 'openai'."
    )


def build_tts_provider() -> TTSProvider:
    """
    Instantiate and return the active TTS provider based on config.TTS_PROVIDER.

    Supported values: "edge" (default), "piper", "elevenlabs".

    Returns:
        A TTSProvider instance.

    Raises:
        ValueError: If an unknown provider name is specified.
    """
    provider_name = config.TTS_PROVIDER.lower()
    if provider_name == "edge":
        from tts.edge_provider import EdgeTTSProvider
        return EdgeTTSProvider()
    if provider_name == "piper":
        from tts.piper_provider import PiperProvider
        return PiperProvider()
    if provider_name == "elevenlabs":
        from tts.elevenlabs_provider import ElevenLabsProvider
        return ElevenLabsProvider()
    raise ValueError(
        f"Unknown TTS_PROVIDER '{config.TTS_PROVIDER}'. "
        "Valid options: 'edge', 'piper', 'elevenlabs'."
    )


def _run_transcription_pipeline(content) -> str:
    """
    Single-voice narration pipeline: read the article aloud in full.

    Skips LLM and dialogue planning entirely — the Markdown is cleaned
    and sent straight to the configured TTS provider, chunk by chunk.
    """
    print("[2/4] Converting to Markdown...")
    markdown_text = convert_to_markdown(content)
    print(f"      Markdown length: {len(markdown_text)} characters")

    print("[3/4] Detecting language...")
    language_code = detect_language(markdown_text)
    print(f"      Detected language: {language_code}")

    print(f"[4/4] Narrating with {config.TTS_PROVIDER} (single voice)...")
    from transcription.narrator import narrate
    tts = build_tts_provider()
    return narrate(
        markdown_text=markdown_text,
        language_code=language_code,
        tts_provider=tts,
        voice="voice_a",
        output_path=config.OUTPUT_PATH,
    )


def _run_notebooklm_pipeline(content) -> str:
    """
    Short-circuit pipeline using Google NotebookLM.

    For URLs: the URL is passed directly to NotebookLM (no pre-scraping).
    For text/file: content is converted to Markdown and sent as a text source.
    Language is always detected before generation to set the audio language.

    Args:
        content: Validated InputContent from handle_input().

    Returns:
        Path to the generated podcast MP3 file.
    """
    print("[2/3] Converting to Markdown for language detection...")
    markdown_text = convert_to_markdown(content)

    print("[2/3] Detecting language...")
    language_code = detect_language(markdown_text)
    print(f"      Detected language: {language_code}")

    print(f"[3/3] Generating podcast via NotebookLM "
          f"({config.NOTEBOOKLM_AUDIO_FORMAT}, {language_code})...")
    from nlm.provider import NotebookLMPodcastProvider
    provider = NotebookLMPodcastProvider()
    output_path = provider.generate(
        content=content,
        language_code=language_code,
        markdown_text=markdown_text,
        output_path=config.OUTPUT_PATH,
    )
    return output_path


def run_pipeline(raw_input: str) -> str:
    """
    Execute the full podcast pipeline on the given raw input.

    Automatically selects the appropriate generation mode:
    - NotebookLM        : when config.PODCAST_PROVIDER == "notebooklm"
    - Simple pipeline   : content ≤ config.LONG_CONTENT_THRESHOLD tokens
    - Hierarchical pipeline : content > threshold (long documents)

    Args:
        raw_input: URL, file path, or plain text to convert.

    Returns:
        Path to the generated podcast MP3 file.
    """
    print("[1/5] Validating and normalising input...")
    content = handle_input(raw_input)
    print(f"      Source type: {content.source_type.value}")

    if config.PODCAST_PROVIDER.lower() == "notebooklm":
        return _run_notebooklm_pipeline(content)

    if config.PODCAST_PROVIDER.lower() == "transcription":
        return _run_transcription_pipeline(content)

    print("[2/5] Converting to Markdown...")
    markdown_text = convert_to_markdown(content)
    print(f"      Markdown length: {len(markdown_text)} characters")

    print("[3/5] Detecting language...")
    language_code = detect_language(markdown_text)
    print(f"      Detected language: {language_code}")

    llm = build_llm_provider()
    token_count = _estimate_tokens(markdown_text)
    is_long = token_count > config.LONG_CONTENT_THRESHOLD

    if is_long:
        print(f"[4/5] Long content detected ({token_count} tokens — threshold: "
              f"{config.LONG_CONTENT_THRESHOLD}). Using hierarchical pipeline...")
        chunks = chunk_markdown(markdown_text, max_tokens=config.CHUNK_MAX_TOKENS)
        print(f"      Split into {len(chunks)} chunk(s).")
        script = generate_script_hierarchical(
            chunks=chunks,
            llm_provider=llm,
            language_code=language_code,
        )
    else:
        print(f"[4/5] Generating podcast script via {config.LLM_PROVIDER} "
              f"({token_count} tokens — simple pipeline)...")
        script = generate_script(
            markdown_text=markdown_text,
            language_code=language_code,
            llm_provider=llm,
        )

    line_count = len([l for l in script.splitlines() if l.strip()])
    print(f"      Script generated: {line_count} lines")

    print("[5/5] Synthesizing audio and building podcast...")
    tts = build_tts_provider()
    output_path = build_podcast(
        dialogue_script=script,
        language_code=language_code,
        tts_provider=tts,
        output_path=config.OUTPUT_PATH,
    )

    return output_path


def main() -> None:
    """Parse CLI arguments and run the pipeline."""
    parser = argparse.ArgumentParser(
        description="Vitruvian Audio Agent — Convert content to podcast.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python app/main.py --text "Inteligência artificial está mudando o mundo."
  python app/main.py --file report.pdf
  python app/main.py --url https://example.com/article
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--text", metavar="TEXT", help="Plain text input")
    input_group.add_argument("--file", metavar="PATH", help="Path to a file (PDF, DOCX, etc.)")
    input_group.add_argument("--url", metavar="URL", help="URL to fetch and convert")

    parser.add_argument(
        "--output",
        metavar="PATH",
        default=None,
        help=f"Output MP3 path (default: {config.OUTPUT_PATH})",
    )

    args = parser.parse_args()

    # Determine raw input string
    if args.text:
        raw_input = args.text
    elif args.file:
        raw_input = args.file
    else:
        raw_input = args.url

    if args.output:
        config.OUTPUT_PATH = args.output

    print("=" * 60)
    print("  Vitruvian Audio Agent — Content → Podcast Pipeline")
    print("=" * 60)

    try:
        output_path = run_pipeline(raw_input)
        print("=" * 60)
        print(f"  ✓ Podcast generated: {output_path}")
        print("=" * 60)
    except RuntimeError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
