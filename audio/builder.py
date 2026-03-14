"""
audio/builder.py — Podcast audio builder.

Converts a dialogue script into a final podcast audio file by:
  1. Parsing each Host1/Host2 line from the script.
  2. Synthesizing audio for each line using the TTS provider.
  3. Combining all segments with a short pause between speakers.
  4. Exporting the merged result (MP3 preferred; WAV fallback if ffmpeg absent).

This is the ONLY place where audio segments are merged (Architecture Invariant #5).
"""

import io
import traceback
from dataclasses import dataclass

from pydub import AudioSegment

import config
from tts.provider import TTSProvider

# Pause duration (ms) inserted between dialogue turns
PAUSE_BETWEEN_SPEAKERS_MS: int = 600

# Voice mapping: dialogue host label → TTS voice identifier
_HOST_VOICE_MAP: dict[str, str] = {
    "Host1": "voice_a",
    "Host2": "voice_b",
}


@dataclass
class DialogueLine:
    """A single parsed line from the dialogue script."""
    host: str
    text: str
    voice: str


def build_podcast(
    dialogue_script: str,
    language_code: str,
    tts_provider: TTSProvider,
    output_path: str | None = None,
) -> str:
    """
    Build and export a podcast audio file from a dialogue script.

    Tries to export as MP3 (requires ffmpeg). If ffmpeg is not available,
    falls back to WAV export (uses Python stdlib only) and adjusts the
    output path extension accordingly.

    Args:
        dialogue_script: Text with alternating Host1/Host2 lines.
        language_code:   Canonical language code propagated to TTS.
        tts_provider:    Concrete TTSProvider instance for audio synthesis.
        output_path:     Destination path for the audio file. Defaults to
                         the value in config.OUTPUT_PATH.

    Returns:
        Absolute path to the generated audio file (.mp3 or .wav).

    Raises:
        ValueError: If the script contains no parseable dialogue lines.
        RuntimeError: Propagated from the TTS provider on synthesis failures.
    """
    output_path = output_path or config.OUTPUT_PATH

    lines = _parse_script(dialogue_script)

    if not lines:
        raise ValueError("Dialogue script contains no parseable Host1/Host2 lines.")

    segments = _synthesize_segments(
        lines=lines,
        language_code=language_code,
        tts_provider=tts_provider,
    )

    podcast = _merge_segments(segments)
    return _export(podcast, output_path)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _export(podcast: AudioSegment, output_path: str) -> str:
    """
    Export the merged podcast to disk as MP3 at the highest available quality.

    Strategy (in order):
      1. pydub + ffmpeg/libmp3lame  — best compatibility, 320 kbps CBR
      2. lameenc (pure Python LAME) — no system dependencies, VBR quality 0
      3. WAV fallback               — lossless, no encoder needed

    Args:
        podcast:     Merged AudioSegment ready for export.
        output_path: Desired output file path (typically ending in .mp3).

    Returns:
        Actual path written to disk (.mp3 or .wav).
    """
    mp3_path = _replace_extension(output_path, ".mp3")

    # --- Attempt 1: ffmpeg via pydub (320 kbps CBR) ---
    try:
        podcast.export(mp3_path, format="mp3", bitrate="320k")
        print("[5/5] Audio exported as MP3 (ffmpeg, 320 kbps).")
        return mp3_path
    except Exception as ffmpeg_err:
        print(f"[5/5] ffmpeg not available ({ffmpeg_err}), trying lameenc…")

    # --- Attempt 2: lameenc pure-Python LAME (VBR quality 0 = highest) ---
    try:
        import lameenc  # noqa: PLC0415

        # Resample to stereo 44100 Hz for maximum MP3 compatibility
        target_rate = 44100
        pcm = podcast.set_frame_rate(target_rate).set_channels(2).set_sample_width(2)

        encoder = lameenc.Encoder()
        encoder.set_bit_rate(320)
        encoder.set_in_sample_rate(target_rate)
        encoder.set_channels(2)
        encoder.set_quality(2)  # 2 = near-best LAME quality; 7 = fastest
        mp3_bytes = encoder.encode(pcm.raw_data) + encoder.flush()

        with open(mp3_path, "wb") as fh:
            fh.write(mp3_bytes)

        print("[5/5] Audio exported as MP3 (lameenc, 320 kbps).")
        return mp3_path
    except Exception as lame_err:
        print(f"[5/5] lameenc failed ({lame_err}), falling back to WAV…")

    # --- Attempt 3: WAV fallback (no encoder needed) ---
    wav_path = _replace_extension(output_path, ".wav")
    try:
        podcast.export(wav_path, format="wav")
        print("[5/5] Audio exported as WAV (lossless fallback).")
        return wav_path
    except Exception as wav_err:
        raise RuntimeError(
            f"All audio export methods failed.\n"
            f"  ffmpeg: {ffmpeg_err}\n"
            f"  lameenc: {lame_err}\n"
            f"  WAV: {wav_err}"
        ) from wav_err


def _replace_extension(path: str, new_ext: str) -> str:
    """Replace the file extension in *path* with *new_ext*."""
    dot = path.rfind(".")
    base = path[:dot] if dot != -1 else path
    return base + new_ext


def _parse_script(script: str) -> list[DialogueLine]:
    """
    Parse a dialogue script into a list of DialogueLine objects.

    Args:
        script: Raw dialogue string with Host1:/Host2: prefixes.

    Returns:
        Ordered list of DialogueLine instances.
    """
    lines: list[DialogueLine] = []

    for raw_line in script.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        for host, voice in _HOST_VOICE_MAP.items():
            prefix = f"{host}:"
            if raw_line.startswith(prefix):
                text = raw_line[len(prefix):].strip()
                if text:
                    lines.append(DialogueLine(host=host, text=text, voice=voice))
                break

    return lines


def _synthesize_segments(
    lines: list[DialogueLine],
    language_code: str,
    tts_provider: TTSProvider,
) -> list[AudioSegment]:
    """
    Synthesize audio for each dialogue line.

    Loads WAV bytes using Python's wave module (no ffmpeg required).
    Non-WAV bytes (MP3, etc.) are passed to pydub's generic loader which
    requires ffmpeg.

    Args:
        lines:         Parsed dialogue lines.
        language_code: Language code propagated to TTS.
        tts_provider:  TTS provider to call per line.

    Returns:
        List of AudioSegment objects in dialogue order.
    """
    segments: list[AudioSegment] = []

    for i, line in enumerate(lines):
        print(f"[DEBUG] TTS line {i+1}/{len(lines)}: {line.host} — voice={line.voice} — text={line.text[:40]!r}…")
        raw_audio: bytes = tts_provider.synthesize(
            text=line.text,
            voice=line.voice,
            language=language_code,
        )
        magic = raw_audio[:4]
        print(f"[DEBUG] TTS line {i+1}: got {len(raw_audio)} bytes, magic={magic!r}")

        # WAV magic bytes: b'RIFF' — load natively without ffmpeg.
        # All other formats (MP3, OGG, …) fall through to pydub's generic
        # loader which delegates to ffmpeg.
        if magic == b"RIFF":
            print(f"[DEBUG] TTS line {i+1}: loading as WAV (no ffmpeg needed)")
            segment = AudioSegment.from_wav(io.BytesIO(raw_audio))
        else:
            print(f"[DEBUG] TTS line {i+1}: loading via pydub generic (needs ffmpeg)")
            segment = AudioSegment.from_file(io.BytesIO(raw_audio))
        print(f"[DEBUG] TTS line {i+1}: loaded OK, duration={len(segment)}ms")
        segments.append(segment)

    return segments


def _merge_segments(segments: list[AudioSegment]) -> AudioSegment:
    """
    Concatenate audio segments with a pause between each speaker turn.

    Args:
        segments: List of individual AudioSegment objects.

    Returns:
        A single merged AudioSegment.
    """
    pause = AudioSegment.silent(duration=PAUSE_BETWEEN_SPEAKERS_MS)
    podcast = segments[0]

    for segment in segments[1:]:
        podcast = podcast + pause + segment

    return podcast
