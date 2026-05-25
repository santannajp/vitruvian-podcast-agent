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
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — ensure project root is on sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402 — must come after sys.path setup
from app.main import run_pipeline  # noqa: E402
from nlm.bootstrap import bootstrap_storage_state  # noqa: E402

# Materialize NotebookLM session from secret (no-op when not configured).
bootstrap_storage_state()

import streamlit as st  # noqa: E402
from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx  # noqa: E402

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Vitruvian Audio Agent",
    page_icon="🎙️",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Access control — no-op when APP_PASSWORD is empty (local dev), gates the
# UI behind a password when set (production / HF Spaces).
# ---------------------------------------------------------------------------
from app.auth import require_password  # noqa: E402
require_password()

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "trim_version" not in st.session_state:
    st.session_state.trim_version = 0
if "nlm_login_pending" not in st.session_state:
    st.session_state.nlm_login_pending = False
if "nlm_pending" not in st.session_state:
    st.session_state.nlm_pending = {}
if "nlm_login_proc" not in st.session_state:
    st.session_state.nlm_login_proc = None
# Background pipeline state
if "_pipeline_running" not in st.session_state:
    st.session_state["_pipeline_running"] = False
if "_pipeline_log" not in st.session_state:
    st.session_state["_pipeline_log"] = []
if "_pipeline_error" not in st.session_state:
    st.session_state["_pipeline_error"] = None
if "_pipeline_result_path" not in st.session_state:
    st.session_state["_pipeline_result_path"] = None
if "_pipeline_done" not in st.session_state:
    st.session_state["_pipeline_done"] = False

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
    _PODCAST_OPTIONS = ["Pipeline (LLM + TTS)", "NotebookLM", "Transcrição (TTS narrado)"]
    _provider_norm = config.PODCAST_PROVIDER.lower()
    if _provider_norm == "notebooklm":
        _podcast_default = 1
    elif _provider_norm == "transcription":
        _podcast_default = 2
    else:
        _podcast_default = 0
    podcast_provider_choice = st.selectbox(
        "Podcast Engine",
        _PODCAST_OPTIONS,
        index=_podcast_default,
        help=(
            "Pipeline — LLM gera diálogo entre dois apresentadores + TTS. "
            "NotebookLM — gerador do Google (requer login). "
            "Transcrição — lê o artigo na íntegra com uma única voz (sem LLM)."
        ),
    )
    use_notebooklm = podcast_provider_choice == "NotebookLM"
    use_transcription = podcast_provider_choice == "Transcrição (TTS narrado)"
    if use_notebooklm:
        config.PODCAST_PROVIDER = "notebooklm"
    elif use_transcription:
        config.PODCAST_PROVIDER = "transcription"
    else:
        config.PODCAST_PROVIDER = ""

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
        # LLM + TTS pipeline (or Transcription — TTS only)
        # ------------------------------------------------------------------
        if use_transcription:
            st.caption(
                "📖 Lê o artigo na íntegra com uma única voz. "
                "Sem LLM, sem geração de diálogo."
            )

        if not use_transcription:
            llm_choice = st.selectbox(
                "LLM Provider",
                ["ollama", "groq", "openai"],
                index=["ollama", "groq", "openai"].index(config.LLM_PROVIDER),
            )
            config.LLM_PROVIDER = llm_choice
        else:
            llm_choice = None

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

        _TTS_OPTIONS = ["edge", "elevenlabs", "piper"]
        _tts_default = config.TTS_PROVIDER if config.TTS_PROVIDER in _TTS_OPTIONS else "edge"
        tts_choice = st.selectbox(
            "TTS Provider",
            _TTS_OPTIONS,
            index=_TTS_OPTIONS.index(_tts_default),
            help="edge — gratuito, sem chave (Microsoft Edge). elevenlabs — premium. piper — local, requer binário.",
        )
        config.TTS_PROVIDER = tts_choice

        if tts_choice == "edge":
            _EDGE_VOICES_PT = [
                "pt-BR-AntonioNeural",
                "pt-BR-FranciscaNeural",
                "pt-BR-ThalitaMultilingualNeural",
            ]
            _va_idx = _EDGE_VOICES_PT.index(config.EDGE_TTS_VOICE_A) if config.EDGE_TTS_VOICE_A in _EDGE_VOICES_PT else 0
            _vb_idx = _EDGE_VOICES_PT.index(config.EDGE_TTS_VOICE_B) if config.EDGE_TTS_VOICE_B in _EDGE_VOICES_PT else 1
            _va_label = "Narrator voice" if use_transcription else "Host1 voice (masculino)"
            voice_a = st.selectbox(_va_label, _EDGE_VOICES_PT, index=_va_idx)
            config.EDGE_TTS_VOICE_A = voice_a
            if not use_transcription:
                voice_b = st.selectbox("Host2 voice (feminino)", _EDGE_VOICES_PT, index=_vb_idx)
                config.EDGE_TTS_VOICE_B = voice_b
            st.caption(
                "Microsoft Edge TTS — gratuito, sem chave. "
                "Vozes pt-BR por padrão; outros idiomas usam vozes nativas automáticas."
            )

        elif tts_choice == "elevenlabs":
            el_key = st.text_input("ElevenLabs API key", value=config.ELEVENLABS_API_KEY, type="password")
            config.ELEVENLABS_API_KEY = el_key
            if not el_key:
                st.warning("Enter your ElevenLabs API key.")

            _el_host1_label = "Narrator voice ID" if use_transcription else "Host1 voice ID"
            el_host1 = st.text_input(
                _el_host1_label,
                value=config.ELEVENLABS_VOICE_HOST1,
                placeholder="21m00Tcm4TlvDq8ikWAM  (Rachel — default)",
            )
            config.ELEVENLABS_VOICE_HOST1 = el_host1

            if not use_transcription:
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

        if not use_transcription:
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
# Thread-safe log writer (captures stdout from background thread)
# ---------------------------------------------------------------------------
class _ThreadSafeWriter:
    """Captures stdout from a background pipeline thread.

    Stores lines in a plain list. The main Streamlit thread reads this
    list on each polling rerun and renders it. This avoids calling
    Streamlit widget APIs from a non-main thread (which is not allowed).
    """

    def __init__(self, log_list: list[str]) -> None:
        self._lines = log_list

    def write(self, text: str) -> None:
        self._lines.append(text)

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
        if "[transcription]" in line.lower() or "single voice" in line.lower():
            pipeline_mode = "transcription"
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
# Audio trim helper
# ---------------------------------------------------------------------------
def _trim_audio(audio_bytes: bytes, audio_mime: str, start_s: float, end_s: float) -> tuple[bytes, str]:
    """Trim audio between start_s and end_s seconds. Returns (trimmed_bytes, mime_type)."""
    from pydub import AudioSegment  # noqa: PLC0415

    if audio_mime == "audio/wav":
        seg = AudioSegment.from_wav(io.BytesIO(audio_bytes))
    else:
        # Use from_file() to handle MP3, M4A/MP4 (NotebookLM output), and other formats.
        seg = AudioSegment.from_file(io.BytesIO(audio_bytes))

    trimmed = seg[int(start_s * 1000) : int(end_s * 1000)]

    # Try MP3 via ffmpeg
    buf = io.BytesIO()
    try:
        trimmed.export(buf, format="mp3", bitrate="320k")
        return buf.getvalue(), "audio/mpeg"
    except Exception:  # noqa: BLE001
        pass

    # Try lameenc (pure Python MP3, no ffmpeg needed)
    try:
        import lameenc  # noqa: PLC0415

        samples = trimmed.get_array_of_samples()
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(320)
        encoder.set_in_sample_rate(trimmed.frame_rate)
        encoder.set_channels(trimmed.channels)
        encoder.set_quality(2)
        mp3_data = encoder.encode(bytes(samples)) + encoder.flush()
        return mp3_data, "audio/mpeg"
    except Exception:  # noqa: BLE001
        pass

    # WAV fallback
    buf = io.BytesIO()
    trimmed.export(buf, format="wav")
    return buf.getvalue(), "audio/wav"


def _fmt_time(s: float) -> str:
    """Format seconds as MM:SS."""
    return f"{int(s // 60):02d}:{int(s % 60):02d}"


# ---------------------------------------------------------------------------
# NotebookLM auth helpers
# ---------------------------------------------------------------------------

def _check_nlm_auth() -> bool:
    """Return True if a NotebookLM storage_state.json exists with a SID cookie.

    Checks both the legacy path (~/.notebooklm/storage_state.json) and the
    profile-based path (~/.notebooklm/profiles/default/storage_state.json)
    used by notebooklm-py >= 0.4.

    Reads the file directly to avoid importing the conflicting local notebooklm/ package.
    No network calls are made.
    """
    import json as _json

    home_env = os.environ.get("NOTEBOOKLM_HOME")
    base_dir = (
        Path(home_env).expanduser().resolve() if home_env else Path.home() / ".notebooklm"
    )

    # Candidate paths: profile-based (new) first, then legacy root
    candidates = [
        base_dir / "profiles" / "default" / "storage_state.json",
        base_dir / "storage_state.json",
    ]

    for storage in candidates:
        if not storage.exists():
            continue
        try:
            data = _json.loads(storage.read_text(encoding="utf-8"))
            if "SID" in {c.get("name") for c in data.get("cookies", [])}:
                return True
        except Exception:  # noqa: BLE001
            continue

    return False


def _start_nlm_login() -> subprocess.Popen:
    """Launch 'notebooklm login' with stdin=PIPE so we can send ENTER later.

    The login command opens a Playwright browser and blocks waiting for the user
    to press ENTER in the terminal.  We send that ENTER via proc.communicate()
    when the user confirms they have finished logging in.

    Raises RuntimeError if the executable cannot be found.
    """
    scripts_dir = Path(sys.executable).parent
    # On Windows the script wrapper has the .exe extension
    exe = scripts_dir / ("notebooklm.exe" if sys.platform == "win32" else "notebooklm")
    cmd = [str(exe), "login"] if exe.exists() else [sys.executable, "-m", "notebooklm", "login"]

    try:
        return subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Could not start `notebooklm login`. "
            "Install with: pip install 'notebooklm-py[browser]' && playwright install chromium"
        ) from exc


# ---------------------------------------------------------------------------
# Pipeline execution — background thread approach
#
# The pipeline (especially Edge TTS transcription) can take 30-120+ seconds.
# Running it synchronously in Streamlit's main thread blocks the WebSocket
# heartbeat, causing the connection to drop and the session_state (including
# the auth flag) to be destroyed — the user sees the login screen.
#
# Solution: launch the pipeline in a daemon thread.  The main thread polls
# every 2 seconds via st.rerun(), keeping the WebSocket alive and rendering
# live progress from the shared log list.
# ---------------------------------------------------------------------------

def _start_pipeline(
    raw_input: str,
    file_bytes: bytes | None = None,
    file_suffix: str | None = None,
) -> None:
    """Prepare temp files and launch the pipeline in a background thread."""
    # Prepare temp input file if needed
    tmp_input_path = None
    if file_bytes is not None:
        tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=file_suffix or "")
        tmp_in.write(file_bytes)
        tmp_in.close()
        tmp_input_path = tmp_in.name
        pipeline_input = tmp_input_path
    else:
        pipeline_input = raw_input

    # Prepare temp output file
    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_out.close()
    config.OUTPUT_PATH = tmp_out.name

    # Reset pipeline state
    log_list: list[str] = []
    st.session_state["_pipeline_running"] = True
    st.session_state["_pipeline_done"] = False
    st.session_state["_pipeline_log"] = log_list
    st.session_state["_pipeline_error"] = None
    st.session_state["_pipeline_result_path"] = None
    st.session_state["_pipeline_tmp_input"] = tmp_input_path

    # Snapshot config values that the sidebar may have changed — the
    # background thread must use these exact values, not whatever the
    # config module holds at the time of a later rerun.
    _cfg_snapshot = {
        "PODCAST_PROVIDER": config.PODCAST_PROVIDER,
        "TTS_PROVIDER": config.TTS_PROVIDER,
        "LLM_PROVIDER": config.LLM_PROVIDER,
        "OUTPUT_PATH": config.OUTPUT_PATH,
    }
    # Edge TTS voice config
    if hasattr(config, "EDGE_TTS_VOICE_A"):
        _cfg_snapshot["EDGE_TTS_VOICE_A"] = config.EDGE_TTS_VOICE_A
        _cfg_snapshot["EDGE_TTS_VOICE_B"] = config.EDGE_TTS_VOICE_B

    def _worker() -> None:
        """Run the pipeline in a background thread."""
        # Apply the config snapshot so sidebar changes during execution
        # don't interfere.
        for k, v in _cfg_snapshot.items():
            setattr(config, k, v)

        writer = _ThreadSafeWriter(log_list)
        try:
            with contextlib.redirect_stdout(writer):  # type: ignore[arg-type]
                output_path = run_pipeline(pipeline_input)
            st.session_state["_pipeline_result_path"] = output_path
        except Exception as exc:  # noqa: BLE001
            st.session_state["_pipeline_error"] = (
                str(exc),
                traceback.format_exc(),
            )
        finally:
            # Clean up temp input
            if tmp_input_path:
                try:
                    os.unlink(tmp_input_path)
                except OSError:
                    pass
            st.session_state["_pipeline_running"] = False
            st.session_state["_pipeline_done"] = True

    thread = threading.Thread(target=_worker, daemon=True)
    # Attach the main script's run context so st.session_state writes from
    # the worker land in this user's session (otherwise they go to a bare
    # fallback state and the main thread polls forever).
    ctx = get_script_run_ctx()
    if ctx is not None:
        add_script_run_ctx(thread, ctx)
    thread.start()


def _finalize_pipeline() -> None:
    """Collect results from the finished background pipeline and store in session_state."""
    error_info = st.session_state.get("_pipeline_error")
    output_path = st.session_state.get("_pipeline_result_path")
    log_list = st.session_state.get("_pipeline_log", [])
    log_text = "".join(log_list)

    # Reset pipeline flags
    st.session_state["_pipeline_done"] = False
    st.session_state["_pipeline_running"] = False

    if error_info:
        error_msg, error_tb = error_info
        st.session_state["_pipeline_error"] = None

        # NotebookLM auth error → trigger login flow
        _err_lower = error_msg.lower()
        if "notebooklm login" in _err_lower or "re-authenticate" in _err_lower or "authentication expired" in _err_lower:
            try:
                st.session_state.nlm_login_proc = _start_nlm_login()
            except RuntimeError as _login_err:
                st.error(str(_login_err))
                st.stop()
            st.session_state.nlm_login_pending = True
            st.rerun()

        st.error(error_msg)
        with st.expander("🐛 Full traceback", expanded=True):
            st.code(error_tb, language="python")
        with st.expander("📋 Pipeline log"):
            st.code(log_text, language="")
        return

    if not output_path or not os.path.exists(output_path):
        st.error("Pipeline finished but no output file was produced.")
        with st.expander("📋 Pipeline log"):
            st.code(log_text, language="")
        return

    language, pipeline_mode, script_lines, chunk_count = _parse_log(log_text)

    is_wav = output_path.endswith(".wav")
    audio_mime = "audio/wav" if is_wav else "audio/mpeg"
    download_name = "podcast.wav" if is_wav else "podcast.mp3"

    try:
        from pydub import AudioSegment  # noqa: PLC0415
        seg = AudioSegment.from_file(output_path)
        duration_s = len(seg) / 1000.0
    except Exception:  # noqa: BLE001
        duration_s = 0.0

    with open(output_path, "rb") as fh:
        audio_bytes = fh.read()

    try:
        os.unlink(output_path)
    except OSError:
        pass

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
    # Clear any lingering login state
    st.session_state.nlm_login_pending = False
    st.session_state.nlm_pending = {}
    st.session_state.nlm_login_proc = None


# ---------------------------------------------------------------------------
# Generate button
# ---------------------------------------------------------------------------
if st.button("🎧 Generate Podcast", type="primary", disabled=(not has_input or st.session_state.get("_pipeline_running"))):
    _file_bytes = uploaded_file.getbuffer().tobytes() if uploaded_file else None
    _file_suffix = Path(uploaded_file.name).suffix if uploaded_file else None
    _text_input = raw_input_value if uploaded_file is None else ""

    # NotebookLM: check authentication first and handle login flow if needed
    if use_notebooklm and not _check_nlm_auth():
        st.session_state.nlm_pending = {
            "text_input": _text_input,
            "file_bytes": _file_bytes,
            "file_suffix": _file_suffix,
        }
        try:
            st.session_state.nlm_login_proc = _start_nlm_login()
        except RuntimeError as _e:
            st.error(str(_e))
            st.stop()
        st.session_state.nlm_login_pending = True
        st.rerun()

    _start_pipeline(_text_input or "", _file_bytes, _file_suffix)
    st.rerun()  # Immediately rerun to enter the polling loop

# ---------------------------------------------------------------------------
# Pipeline progress polling — keeps WebSocket alive during long operations
# ---------------------------------------------------------------------------
if st.session_state.get("_pipeline_running"):
    _log_lines = st.session_state.get("_pipeline_log", [])
    with st.status("🎙️ Generating your podcast…", expanded=True):
        st.code("".join(_log_lines) or "Starting…", language="")
    # Sleep briefly then rerun — this is the key to keeping the
    # Streamlit WebSocket alive during long operations.
    time.sleep(2)
    st.rerun()

# Pipeline just finished — collect results
if st.session_state.get("_pipeline_done"):
    _finalize_pipeline()
    st.rerun()  # Rerun to render the results section

# ---------------------------------------------------------------------------
# NotebookLM login flow (shown while waiting for the user to finish OAuth)
# ---------------------------------------------------------------------------
if st.session_state.nlm_login_pending:
    st.divider()
    st.warning(
        "🔐 **NotebookLM login required.**\n\n"
        "A browser window has opened — sign in with your Google account.\n"
        "Once you see the **NotebookLM homepage**, click the button below."
    )
    _col_ok, _col_cancel = st.columns([3, 1])

    if _col_ok.button("✅ Já fiz login — continuar", type="primary"):
        _proc: subprocess.Popen | None = st.session_state.nlm_login_proc
        if _proc is not None:
            with st.spinner("Salvando credenciais…"):
                try:
                    # Send ENTER to unblock the 'notebooklm login' prompt,
                    # which then saves storage_state.json and exits.
                    _proc.communicate(input=b"\n", timeout=20)
                except subprocess.TimeoutExpired:
                    _proc.kill()
                except Exception:  # noqa: BLE001
                    pass
            st.session_state.nlm_login_proc = None

        if _check_nlm_auth():
            _pending = st.session_state.nlm_pending or {}
            st.session_state.nlm_login_pending = False
            st.session_state.nlm_pending = {}
            _start_pipeline(
                _pending.get("text_input") or "",
                _pending.get("file_bytes"),
                _pending.get("file_suffix"),
            )
            st.rerun()
        else:
            st.error(
                "Login não detectado. Certifique-se de ter concluído o login no Google "
                "e de estar vendo a página inicial do NotebookLM antes de clicar no botão."
            )

    if _col_cancel.button("✖ Cancelar"):
        _proc = st.session_state.nlm_login_proc
        if _proc is not None:
            try:
                _proc.kill()
            except Exception:  # noqa: BLE001
                pass
        st.session_state.nlm_login_pending = False
        st.session_state.nlm_pending = {}
        st.session_state.nlm_login_proc = None
        st.rerun()

# ---------------------------------------------------------------------------
# Results (persistent across re-renders via session_state)
# ---------------------------------------------------------------------------
if st.session_state.result:
    r = st.session_state.result
    duration_s: float = r.get("edited_duration_s") or r["duration_s"]
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
    elif r["pipeline_mode"] == "transcription":
        col3.metric("Engine", "Transcrição")
        col4.metric("TTS", config.TTS_PROVIDER)
    else:
        col3.metric("Dialogue lines", r["script_lines"])
        col4.metric("Pipeline", r["pipeline_mode"].title())

    if r["pipeline_mode"] == "hierarchical":
        st.info(f"Long content processed in **{r['chunk_count']} chunk(s)** using the hierarchical pipeline.")

    # Determine current audio (edited or original)
    _display_bytes = r.get("edited_bytes") or r["audio_bytes"]
    _display_mime = r.get("edited_mime") or r["audio_mime"]
    _display_name = r.get("edited_name") or r["download_name"]
    _display_duration = r.get("edited_duration_s") or r["duration_s"]

    # Audio player
    st.audio(_display_bytes, format=_display_mime)

    # ---- Trim editor ----
    with st.expander("✂️ Trim Audio", expanded=bool(r.get("edited_bytes"))):
        _dur = float(_display_duration)

        if _dur <= 0.5:
            st.info("Audio duration could not be determined. Trim is unavailable.")
        else:
            trim_range = st.slider(
                "Select range to keep",
                min_value=0.0,
                max_value=_dur,
                value=(0.0, _dur),
                step=0.5,
                format="%.1f s",
                key=f"trim_{st.session_state.trim_version}",
            )
            start_s_trim, end_s_trim = trim_range
            st.caption(
                f"Selected: **{_fmt_time(start_s_trim)}** → **{_fmt_time(end_s_trim)}**  "
                f"(duration: {_fmt_time(end_s_trim - start_s_trim)})"
            )

            col_apply, col_reset, _ = st.columns([2, 2, 4])

            if col_apply.button("✂️ Apply trim", type="primary"):
                with st.spinner("Trimming…"):
                    _edited_bytes, _edited_mime = _trim_audio(
                        _display_bytes, _display_mime, start_s_trim, end_s_trim
                    )
                _is_wav_edit = _edited_mime == "audio/wav"
                _edited_name = "podcast_edited.wav" if _is_wav_edit else "podcast_edited.mp3"
                try:
                    from pydub import AudioSegment  # noqa: PLC0415

                    _edited_dur = len(AudioSegment.from_file(io.BytesIO(_edited_bytes))) / 1000.0
                except Exception:  # noqa: BLE001
                    _edited_dur = end_s_trim - start_s_trim
                r["edited_bytes"] = _edited_bytes
                r["edited_mime"] = _edited_mime
                r["edited_name"] = _edited_name
                r["edited_duration_s"] = _edited_dur
                st.session_state.trim_version += 1
                st.rerun()

            if r.get("edited_bytes") is not None:
                if col_reset.button("↩️ Reset"):
                    for _k in ["edited_bytes", "edited_mime", "edited_name", "edited_duration_s"]:
                        r.pop(_k, None)
                    st.session_state.trim_version += 1
                    st.rerun()
                st.success("Audio trimmed. Download the edited version below.")

    # Download button — uses edited audio when available
    st.download_button(
        label=f"⬇️ Download {_display_name}",
        data=_display_bytes,
        file_name=_display_name,
        mime=_display_mime,
    )

    # Pipeline log (collapsed by default)
    with st.expander("📋 Pipeline log"):
        st.code(r["log"], language="")

    # Button to reset and generate a new podcast
    if st.button("🔄 Generate another podcast"):
        st.session_state.result = None
        st.rerun()
