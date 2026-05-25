"""
transcription/narrator.py — Read the full article aloud with a single voice.

No LLM, no dialogue planning. The Markdown is stripped to plain text,
split into TTS-sized chunks, synthesized one by one with a single voice,
and concatenated into the final podcast file.
"""

import gc
import io
import re

from pydub import AudioSegment

import config
from tts.provider import TTSProvider


# Smaller chunks reduce the chance of the Edge TTS websocket timing out
# mid-stream on long narrations. Most cloud TTS APIs accept much more,
# but the public Edge endpoint is the limiting factor.
_MAX_CHUNK_CHARS: int = 1800
# Short pause inserted between consecutive synthesized chunks.
_PAUSE_BETWEEN_CHUNKS_MS: int = 400


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def narrate(
    markdown_text: str,
    language_code: str,
    tts_provider: TTSProvider,
    voice: str = "voice_a",
    output_path: str | None = None,
) -> str:
    """
    Convert *markdown_text* into a single-voice narrated audio file.

    Args:
        markdown_text: Source content in Markdown.
        language_code: Canonical language code (e.g. "pt-BR", "en").
        tts_provider:  Concrete TTSProvider used for synthesis.
        voice:         Voice identifier ("voice_a" or "voice_b").
        output_path:   Destination path. Defaults to config.OUTPUT_PATH.

    Returns:
        Absolute path to the generated audio file (.mp3 or .wav).

    Raises:
        ValueError: If the cleaned text is empty.
    """
    output_path = output_path or config.OUTPUT_PATH

    plain_text = _markdown_to_plain(markdown_text)
    if not plain_text:
        raise ValueError("Transcription input is empty after Markdown cleanup.")

    chunks = _split_for_tts(plain_text, _MAX_CHUNK_CHARS)
    print(f"      [Transcription] Cleaned text: {len(plain_text)} chars → {len(chunks)} chunk(s).")

    # Stream-merge: synthesize each chunk, append to the running podcast,
    # then drop the chunk so peak memory stays roughly the size of the final
    # audio (instead of N copies, which OOM-kills small instances).
    pause = AudioSegment.silent(duration=_PAUSE_BETWEEN_CHUNKS_MS)
    podcast: AudioSegment | None = None

    for i, chunk in enumerate(chunks, start=1):
        print(f"      [Transcription] Synthesizing chunk {i}/{len(chunks)} ({len(chunk)} chars)…")
        raw_audio = tts_provider.synthesize(text=chunk, voice=voice, language=language_code)
        if raw_audio[:4] == b"RIFF":
            seg = AudioSegment.from_wav(io.BytesIO(raw_audio))
        else:
            seg = AudioSegment.from_file(io.BytesIO(raw_audio))
        del raw_audio

        podcast = seg if podcast is None else podcast + pause + seg
        del seg
        gc.collect()

    return _export(podcast, output_path)


# ---------------------------------------------------------------------------
# Markdown cleanup
# ---------------------------------------------------------------------------

def _markdown_to_plain(md: str) -> str:
    """
    Strip Markdown formatting and return clean prose suitable for TTS.

    Removes images, link syntax (keeping the link text), code fences and
    inline code markers, headings markers, blockquote markers, list bullets,
    emphasis markers, and HTML tags. Collapses runs of blank lines so each
    paragraph stays separated by a single blank line — this helps TTS
    engines insert natural pauses.
    """
    text = md

    # Remove fenced code blocks entirely (TTS reading random code is noise).
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    # Remove inline code backticks (keep the content).
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Images: ![alt](url) → drop entirely.
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    # Links: [text](url) → keep just "text".
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Reference-style links / bare URLs in angle brackets.
    text = re.sub(r"<https?://[^>]+>", "", text)
    text = re.sub(r"https?://\S+", "", text)

    # HTML tags.
    text = re.sub(r"<[^>]+>", "", text)

    # Headings: drop leading # characters but keep the text on its own line.
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)

    # Blockquote markers.
    text = re.sub(r"^\s*>\s?", "", text, flags=re.MULTILINE)

    # List bullets (-, *, +, "1.", etc.).
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Horizontal rules.
    text = re.sub(r"^\s*[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Emphasis markers (**bold**, *italic*, __bold__, _italic_, ~~strike~~).
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    text = re.sub(r"(?<!_)_([^_\n]+)_(?!_)", r"\1", text)
    text = re.sub(r"~~([^~]+)~~", r"\1", text)

    # Pipe tables: replace pipes with spaces so cells become inline phrases.
    text = re.sub(r"\|", " ", text)

    # Collapse 3+ newlines into 2 (paragraph break).
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse runs of spaces/tabs (but not newlines).
    text = re.sub(r"[ \t]+", " ", text)
    # Trim each line.
    text = "\n".join(line.strip() for line in text.splitlines())
    # Re-collapse any blank lines created by the trim step.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _split_for_tts(text: str, max_chars: int) -> list[str]:
    """
    Split *text* into pieces no larger than *max_chars*, preferring to break
    on paragraph boundaries, then sentence boundaries, then word boundaries.
    """
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    paragraphs = text.split("\n\n")
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        # Flush whatever we had accumulated.
        if current:
            chunks.append(current)
            current = ""

        # Paragraph itself fits — start a new accumulator with it.
        if len(para) <= max_chars:
            current = para
            continue

        # Paragraph too large on its own — break on sentence boundaries.
        for piece in _split_paragraph(para, max_chars):
            if len(piece) <= max_chars:
                chunks.append(piece)
            else:
                chunks.extend(_hard_wrap(piece, max_chars))

    if current:
        chunks.append(current)

    return chunks


def _split_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Break a long paragraph at sentence terminators (. ! ? …)."""
    sentences = re.split(r"(?<=[.!?…])\s+", paragraph)
    out: list[str] = []
    current = ""
    for sent in sentences:
        candidate = f"{current} {sent}".strip() if current else sent
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                out.append(current)
            current = sent
    if current:
        out.append(current)
    return out


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    """Last-resort splitter: break on word boundaries by character budget."""
    words = text.split()
    out: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                out.append(current)
            # Word longer than max_chars (rare) — slice it raw.
            if len(word) > max_chars:
                for i in range(0, len(word), max_chars):
                    out.append(word[i : i + max_chars])
                current = ""
            else:
                current = word
    if current:
        out.append(current)
    return out


# ---------------------------------------------------------------------------
# Audio export
# ---------------------------------------------------------------------------

def _export(podcast: AudioSegment, output_path: str) -> str:
    """Export to MP3 (ffmpeg → lameenc → WAV fallback). Mirrors audio/builder.py."""
    mp3_path = _replace_extension(output_path, ".mp3")

    try:
        podcast.export(mp3_path, format="mp3", bitrate="320k")
        print("[Transcription] Audio exported as MP3 (ffmpeg, 320 kbps).")
        return mp3_path
    except Exception as ffmpeg_err:
        print(f"[Transcription] ffmpeg not available ({ffmpeg_err}), trying lameenc…")

    try:
        import lameenc  # noqa: PLC0415

        target_rate = 44100
        pcm = podcast.set_frame_rate(target_rate).set_channels(2).set_sample_width(2)
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(320)
        encoder.set_in_sample_rate(target_rate)
        encoder.set_channels(2)
        encoder.set_quality(2)
        mp3_bytes = encoder.encode(pcm.raw_data) + encoder.flush()
        with open(mp3_path, "wb") as fh:
            fh.write(mp3_bytes)
        print("[Transcription] Audio exported as MP3 (lameenc, 320 kbps).")
        return mp3_path
    except Exception as lame_err:
        print(f"[Transcription] lameenc failed ({lame_err}), falling back to WAV…")

    wav_path = _replace_extension(output_path, ".wav")
    podcast.export(wav_path, format="wav")
    print("[Transcription] Audio exported as WAV (lossless fallback).")
    return wav_path


def _replace_extension(path: str, new_ext: str) -> str:
    dot = path.rfind(".")
    base = path[:dot] if dot != -1 else path
    return base + new_ext
