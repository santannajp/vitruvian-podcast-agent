"""
app/streamlit_app.py — Streamlit frontend for the Vitruvian Audio Agent.

Allows the user to submit a URL, upload a file, or paste text, then
generates a podcast and offers a player and download button.

Run with:
    streamlit run app/streamlit_app.py
"""

import contextlib
import io
import os
import sys
import tempfile
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — ensure project root is on sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402 — must come after sys.path setup
from app.main import run_pipeline  # noqa: E402

import streamlit as st  # noqa: E402

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Vitruvian Audio Agent",
    page_icon="🎙️",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🎙️ Vitruvian Audio Agent")
st.caption("Transform any written content into a conversational podcast.")

# ---------------------------------------------------------------------------
# Sidebar — provider selection (overrides config at runtime)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Providers")

    # ------------------------------------------------------------------
    # Top-level: NotebookLM vs. local LLM + TTS pipeline
    # ------------------------------------------------------------------
    _PODCAST_OPTIONS = ["Pipeline (LLM + TTS)", "NotebookLM"]
    _podcast_default = 1 if config.PODCAST_PROVIDER.lower() == "notebooklm" else 0
    podcast_provider_choice = st.selectbox(
        "Podcast Engine",
        _PODCAST_OPTIONS,
        index=_podcast_default,
        help="NotebookLM — Google's AI podcast generator (requires login). Pipeline — local LLM + TTS.",
    )
    use_notebooklm = podcast_provider_choice == "NotebookLM"
    config.PODCAST_PROVIDER = "notebooklm" if use_notebooklm else ""

    st.divider()

    if use_notebooklm:
        # ------------------------------------------------------------------
        # NotebookLM options
        # ------------------------------------------------------------------
        st.caption("🔐 Requires `notebooklm login` (one-time browser auth).")

        _FORMAT_OPTIONS = ["deep-dive", "brief", "critique", "debate"]
        _fmt_default = (
            _FORMAT_OPTIONS.index(config.NOTEBOOKLM_AUDIO_FORMAT)
            if config.NOTEBOOKLM_AUDIO_FORMAT in _FORMAT_OPTIONS
            else 0
        )
        nlm_format = st.selectbox(
            "Audio format",
            _FORMAT_OPTIONS,
            index=_fmt_default,
            help="deep-dive — detailed discussion. brief — concise. critique — critical analysis. debate — opposing views.",
        )
        config.NOTEBOOKLM_AUDIO_FORMAT = nlm_format

        _LENGTH_OPTIONS = ["short", "default", "long"]
        _len_default = (
            _LENGTH_OPTIONS.index(config.NOTEBOOKLM_AUDIO_LENGTH)
            if config.NOTEBOOKLM_AUDIO_LENGTH in _LENGTH_OPTIONS
            else 1
        )
        nlm_length = st.selectbox("Audio length", _LENGTH_OPTIONS, index=_len_default)
        config.NOTEBOOKLM_AUDIO_LENGTH = nlm_length

        nlm_instructions = st.text_input(
            "Custom instructions (optional)",
            value=config.NOTEBOOKLM_INSTRUCTIONS,
            placeholder="e.g. focus on practical applications",
        )
        config.NOTEBOOKLM_INSTRUCTIONS = nlm_instructions

    else:
        # ------------------------------------------------------------------
        # Existing LLM + TTS pipeline options
        # ------------------------------------------------------------------
        llm_choice = st.selectbox(
            "LLM Provider",
            ["ollama", "groq", "openai"],
            index=["ollama", "groq", "openai"].index(config.LLM_PROVIDER),
        )
        config.LLM_PROVIDER = llm_choice

        if llm_choice == "ollama":
            ollama_model = st.text_input("Ollama model", value=config.OLLAMA_MODEL)
            config.OLLAMA_MODEL = ollama_model
            ollama_url = st.text_input("Ollama URL", value=config.OLLAMA_BASE_URL)
            config.OLLAMA_BASE_URL = ollama_url

        elif llm_choice == "groq":
            groq_key = st.text_input("Groq API key", value=config.GROQ_API_KEY, type="password")
            config.GROQ_API_KEY = groq_key
            groq_model = st.text_input("Groq model", value=config.GROQ_MODEL)
            config.GROQ_MODEL = groq_model
            if not groq_key:
                st.warning("Enter your Groq API key.")

        elif llm_choice == "openai":
            oai_key = st.text_input("OpenAI API key", value=config.OPENAI_API_KEY, type="password")
            config.OPENAI_API_KEY = oai_key
            oai_model = st.text_input("OpenAI model", value=config.OPENAI_MODEL)
            config.OPENAI_MODEL = oai_model
            if not oai_key:
                st.warning("Enter your OpenAI API key.")

        st.divider()

        _TTS_OPTIONS = ["openai", "elevenlabs", "piper"]
        _tts_default = config.TTS_PROVIDER if config.TTS_PROVIDER in _TTS_OPTIONS else "openai"
        tts_choice = st.selectbox(
            "TTS Provider",
            _TTS_OPTIONS,
            index=_TTS_OPTIONS.index(_tts_default),
            help="openai — best quality, uses your OpenAI key. elevenlabs — premium voices. piper — local, requires binary.",
        )
        config.TTS_PROVIDER = tts_choice

        if tts_choice == "openai":
            _OPENAI_VOICES = ["onyx", "nova", "alloy", "echo", "fable", "shimmer", "ash", "ballad", "coral", "sage"]
            _va_idx = _OPENAI_VOICES.index(config.OPENAI_TTS_VOICE_A) if config.OPENAI_TTS_VOICE_A in _OPENAI_VOICES else 0
            _vb_idx = _OPENAI_VOICES.index(config.OPENAI_TTS_VOICE_B) if config.OPENAI_TTS_VOICE_B in _OPENAI_VOICES else 1
            voice_a = st.selectbox("Host1 voice (masculino)", _OPENAI_VOICES, index=_va_idx)
            config.OPENAI_TTS_VOICE_A = voice_a
            voice_b = st.selectbox("Host2 voice (feminino)", _OPENAI_VOICES, index=_vb_idx)
            config.OPENAI_TTS_VOICE_B = voice_b
            st.caption("Modelo: tts-1-hd · Usa a OPENAI_API_KEY acima.")

        elif tts_choice == "elevenlabs":
            el_key = st.text_input("ElevenLabs API key", value=config.ELEVENLABS_API_KEY, type="password")
            config.ELEVENLABS_API_KEY = el_key
            if not el_key:
                st.warning("Enter your ElevenLabs API key.")

            el_host1 = st.text_input(
                "Host1 voice ID",
                value=config.ELEVENLABS_VOICE_HOST1,
                placeholder="21m00Tcm4TlvDq8ikWAM  (Rachel — default)",
            )
            config.ELEVENLABS_VOICE_HOST1 = el_host1

            el_host2 = st.text_input(
                "Host2 voice ID",
                value=config.ELEVENLABS_VOICE_HOST2,
                placeholder="pNInz6obpgDQGcFmaJgB  (Adam — default)",
            )
            config.ELEVENLABS_VOICE_HOST2 = el_host2
            st.warning(
                "⚠️ **ElevenLabs free plan** does not allow using library voices (Rachel, Adam, etc.) "
                "via API. You must enter the ID of a voice **created in your own account**, or upgrade "
                "to a paid plan.\n\n"
                "**Recommended alternative:** switch TTS Provider to **openai** — same key, no extra cost."
            )

        elif tts_choice == "piper":
            st.caption("Requires the Piper binary installed locally (`piper` on PATH).")

        st.divider()
        st.markdown(f"**Chunk size:** {config.CHUNK_MAX_TOKENS} tokens")
        st.markdown(f"**Long content threshold:** {config.LONG_CONTENT_THRESHOLD} tokens")

# ---------------------------------------------------------------------------
# Input selection
# ---------------------------------------------------------------------------
st.subheader("Input")
input_type = st.radio(
    "Choose how to provide content:",
    ["🔗 URL", "📄 File upload", "✍️ Text"],
    horizontal=True,
    label_visibility="collapsed",
)

raw_input_value: str | None = None
uploaded_file = None

if "URL" in input_type:
    raw_input_value = st.text_input(
        "URL",
        placeholder="https://example.com/article",
        label_visibility="collapsed",
    ).strip() or None

elif "File" in input_type:
    uploaded_file = st.file_uploader(
        "Upload a file",
        type=["pdf", "docx", "txt", "pptx", "xlsx", "html", "md", "csv"],
        label_visibility="collapsed",
    )
    if uploaded_file:
        st.success(f"Ready: **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")

else:  # Text
    text_val = st.text_area(
        "Paste your text here",
        height=220,
        placeholder="Paste an article, research notes, or any text...",
        label_visibility="collapsed",
    )
    raw_input_value = text_val.strip() or None

has_input = bool(raw_input_value) or (uploaded_file is not None)

# ---------------------------------------------------------------------------
# Real-time log writer (streams run_pipeline prints into the UI)
# ---------------------------------------------------------------------------
class _StreamlitWriter:
    """Redirects stdout to a Streamlit code block, updating it live."""

    def __init__(self, container: st.delta_generator.DeltaGenerator) -> None:
        self._container = container
        self._lines: list[str] = []

    def write(self, text: str) -> None:
        self._lines.append(text)
        self._container.code("".join(self._lines), language="")

    def flush(self) -> None:  # required by redirect_stdout
        pass

    def getvalue(self) -> str:
        return "".join(self._lines)


# ---------------------------------------------------------------------------
# Helper — extract metadata from captured log text
# ---------------------------------------------------------------------------
def _parse_log(log: str) -> tuple[str, str, int, int]:
    """Return (language_code, pipeline_mode, script_lines, chunk_count)."""
    language = "unknown"
    pipeline_mode = "simple"
    script_lines = 0
    chunk_count = 1

    for line in log.splitlines():
        if "Detected language:" in line:
            language = line.split("Detected language:")[-1].strip()
        if "notebooklm" in line.lower():
            pipeline_mode = "notebooklm"
        if "hierarchical pipeline" in line.lower():
            pipeline_mode = "hierarchical"
        if "Split into" in line:
            try:
                chunk_count = int(line.split("Split into")[1].split("chunk")[0].strip())
            except ValueError:
                pass
        if "Script generated:" in line:
            try:
                script_lines = int(
                    line.split("Script generated:")[1].split("lines")[0].strip()
                )
            except ValueError:
                pass

    return language, pipeline_mode, script_lines, chunk_count


# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------
if st.button("🎧 Generate Podcast", type="primary", disabled=not has_input):
    # Resolve raw_input: save uploaded file to a temp path if needed
    tmp_input_path: str | None = None
    if uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix
        tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_in.write(uploaded_file.getbuffer())
        tmp_in.close()
        tmp_input_path = tmp_in.name
        raw_input = tmp_input_path
    else:
        raw_input = raw_input_value  # type: ignore[assignment]

    # Temporary output MP3
    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_out.close()
    config.OUTPUT_PATH = tmp_out.name

    # Run pipeline with live log streaming
    with st.status("🎙️ Generating your podcast…", expanded=True) as status:
        log_box = st.empty()
        writer = _StreamlitWriter(log_box)
        error: Exception | None = None

        try:
            with contextlib.redirect_stdout(writer):  # type: ignore[arg-type]
                output_path = run_pipeline(raw_input)
            status.update(label="✅ Podcast generated!", state="complete")
        except Exception as exc:  # noqa: BLE001
            error = exc
            error_tb = traceback.format_exc()
            status.update(label=f"❌ Error: {exc}", state="error")

    # Cleanup temp input file
    if tmp_input_path:
        try:
            os.unlink(tmp_input_path)
        except OSError:
            pass

    if error:
        st.error(str(error))
        with st.expander("🐛 Full traceback", expanded=True):
            st.code(error_tb, language="python")
        st.stop()

    # Parse metadata from log
    log_text = writer.getvalue()
    language, pipeline_mode, script_lines, chunk_count = _parse_log(log_text)

    # Detect actual output format (builder falls back to WAV when ffmpeg absent)
    is_wav = output_path.endswith(".wav")
    audio_mime = "audio/wav" if is_wav else "audio/mpeg"
    download_name = "podcast.wav" if is_wav else "podcast.mp3"

    # Get audio duration via pydub
    try:
        from pydub import AudioSegment  # noqa: PLC0415

        if is_wav:
            audio_seg = AudioSegment.from_wav(output_path)
        else:
            audio_seg = AudioSegment.from_mp3(output_path)
        duration_s = len(audio_seg) / 1000.0
    except Exception:  # noqa: BLE001
        duration_s = 0.0

    # Read audio bytes
    with open(output_path, "rb") as fh:
        audio_bytes = fh.read()

    # Remove temp output file (bytes already in memory)
    try:
        os.unlink(output_path)
    except OSError:
        pass

    # Persist results so they survive re-renders
    st.session_state.result = {
        "audio_bytes": audio_bytes,
        "audio_mime": audio_mime,
        "download_name": download_name,
        "language": language,
        "pipeline_mode": pipeline_mode,
        "script_lines": script_lines,
        "chunk_count": chunk_count,
        "duration_s": duration_s,
        "log": log_text,
    }

# ---------------------------------------------------------------------------
# Results (persistent across re-renders via session_state)
# ---------------------------------------------------------------------------
if st.session_state.result:
    r = st.session_state.result
    duration_s: float = r["duration_s"]
    duration_fmt = f"{int(duration_s // 60)}m {int(duration_s % 60)}s" if duration_s else "—"

    st.divider()
    st.subheader("🎙️ Your Podcast")

    # Metadata metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Language", r["language"])
    col2.metric("Duration", duration_fmt)
    if r["pipeline_mode"] == "notebooklm":
        col3.metric("Engine", "NotebookLM")
        col4.metric("Format", config.NOTEBOOKLM_AUDIO_FORMAT)
    else:
        col3.metric("Dialogue lines", r["script_lines"])
        col4.metric("Pipeline", r["pipeline_mode"].title())

    if r["pipeline_mode"] == "hierarchical":
        st.info(f"Long content processed in **{r['chunk_count']} chunk(s)** using the hierarchical pipeline.")

    # Audio player
    st.audio(r["audio_bytes"], format=r["audio_mime"])

    # Download button
    st.download_button(
        label=f"⬇️ Download {r['download_name']}",
        data=r["audio_bytes"],
        file_name=r["download_name"],
        mime=r["audio_mime"],
    )

    # Pipeline log (collapsed by default)
    with st.expander("📋 Pipeline log"):
        st.code(r["log"], language="")

    # Button to reset and generate a new podcast
    if st.button("🔄 Generate another podcast"):
        st.session_state.result = None
        st.rerun()
