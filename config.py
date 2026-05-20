"""
config.py — Centralized configuration loader.

All modules must import config values from here.
No module should read os.environ directly.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (one level up from this file if needed,
# but config.py sits at the root).
load_dotenv(dotenv_path=Path(__file__).parent / ".env")


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")

# ---------------------------------------------------------------------------
# Piper TTS
# ---------------------------------------------------------------------------
PIPER_EXECUTABLE: str = os.getenv("PIPER_EXECUTABLE", "piper")

# pt-BR (default / fallback)
PIPER_MODEL_HOST1: str = os.getenv("PIPER_MODEL_HOST1", "models/pt_BR-faber-medium.onnx")
PIPER_MODEL_HOST2: str = os.getenv("PIPER_MODEL_HOST2", "models/pt_BR-edresson-low.onnx")

# Phase 4 — per-language Piper models
PIPER_MODEL_EN_HOST1: str = os.getenv("PIPER_MODEL_EN_HOST1", "models/en_US-lessac-medium.onnx")
PIPER_MODEL_EN_HOST2: str = os.getenv("PIPER_MODEL_EN_HOST2", "models/en_US-kusal-medium.onnx")
PIPER_MODEL_ES_HOST1: str = os.getenv("PIPER_MODEL_ES_HOST1", "models/es_ES-sharvard-medium.onnx")
PIPER_MODEL_ES_HOST2: str = os.getenv("PIPER_MODEL_ES_HOST2", "models/es_ES-sharvard-medium.onnx")
PIPER_MODEL_ZH_HOST1: str = os.getenv("PIPER_MODEL_ZH_HOST1", "models/zh_CN-huayan-medium.onnx")
PIPER_MODEL_ZH_HOST2: str = os.getenv("PIPER_MODEL_ZH_HOST2", "models/zh_CN-huayan-medium.onnx")
PIPER_MODEL_RU_HOST1: str = os.getenv("PIPER_MODEL_RU_HOST1", "models/ru_RU-denis-medium.onnx")
PIPER_MODEL_RU_HOST2: str = os.getenv("PIPER_MODEL_RU_HOST2", "models/ru_RU-irina-medium.onnx")

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
OUTPUT_PATH: str = os.getenv("OUTPUT_PATH", "podcast.mp3")

# ---------------------------------------------------------------------------
# Phase 2 — Long Content Handling
# ---------------------------------------------------------------------------
# Maximum estimated tokens per chunk (1000–2000 recommended by claude.md)
CHUNK_MAX_TOKENS: int = int(os.getenv("CHUNK_MAX_TOKENS", "1500"))
# Token threshold above which the hierarchical pipeline is activated
LONG_CONTENT_THRESHOLD: int = int(os.getenv("LONG_CONTENT_THRESHOLD", "3000"))

# ---------------------------------------------------------------------------
# API providers (Phase 3 — optional in Phase 1)
# ---------------------------------------------------------------------------
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")

# Default (pt-BR) ElevenLabs voices
ELEVENLABS_VOICE_HOST1: str = os.getenv("ELEVENLABS_VOICE_HOST1", "")
ELEVENLABS_VOICE_HOST2: str = os.getenv("ELEVENLABS_VOICE_HOST2", "")

# Phase 4 — per-language ElevenLabs voice IDs (optional; fallback to defaults)
ELEVENLABS_VOICE_EN_HOST1: str = os.getenv("ELEVENLABS_VOICE_EN_HOST1", "")
ELEVENLABS_VOICE_EN_HOST2: str = os.getenv("ELEVENLABS_VOICE_EN_HOST2", "")
ELEVENLABS_VOICE_ES_HOST1: str = os.getenv("ELEVENLABS_VOICE_ES_HOST1", "")
ELEVENLABS_VOICE_ES_HOST2: str = os.getenv("ELEVENLABS_VOICE_ES_HOST2", "")
ELEVENLABS_VOICE_ZH_HOST1: str = os.getenv("ELEVENLABS_VOICE_ZH_HOST1", "")
ELEVENLABS_VOICE_ZH_HOST2: str = os.getenv("ELEVENLABS_VOICE_ZH_HOST2", "")
ELEVENLABS_VOICE_RU_HOST1: str = os.getenv("ELEVENLABS_VOICE_RU_HOST1", "")
ELEVENLABS_VOICE_RU_HOST2: str = os.getenv("ELEVENLABS_VOICE_RU_HOST2", "")

# Model names for cloud providers
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2")

# OpenAI TTS voices and model
# Available voices: alloy, echo, fable, onyx, nova, shimmer, ash, ballad, coral, sage
OPENAI_TTS_MODEL: str = os.getenv("OPENAI_TTS_MODEL", "tts-1-hd")
OPENAI_TTS_VOICE_A: str = os.getenv("OPENAI_TTS_VOICE_A", "onyx")   # Host1 — deep male
OPENAI_TTS_VOICE_B: str = os.getenv("OPENAI_TTS_VOICE_B", "nova")   # Host2 — warm female

# Microsoft Edge TTS — free, no API key.
# Defaults target pt-BR. Override via .env or sidebar for other languages.
EDGE_TTS_VOICE_A: str = os.getenv("EDGE_TTS_VOICE_A", "pt-BR-AntonioNeural")     # Host1 — male
EDGE_TTS_VOICE_B: str = os.getenv("EDGE_TTS_VOICE_B", "pt-BR-FranciscaNeural")   # Host2 — female

# ---------------------------------------------------------------------------
# Provider selection (Phase 3)
# ---------------------------------------------------------------------------
# Set LLM_PROVIDER to: "ollama" | "groq" | "openai"
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
# Set TTS_PROVIDER to: "piper" | "elevenlabs"
TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "piper")

# ---------------------------------------------------------------------------
# NotebookLM provider (optional — replaces LLM + TTS pipeline entirely)
# ---------------------------------------------------------------------------
# Set PODCAST_PROVIDER to "notebooklm" to use Google NotebookLM directly.
# Leave empty (default) to use the existing LLM + TTS pipeline.
# Requires: pip install "notebooklm-py[browser]" && playwright install chromium && notebooklm login
PODCAST_PROVIDER: str = os.getenv("PODCAST_PROVIDER", "")

# Audio format: "deep-dive" | "brief" | "critique" | "debate"
NOTEBOOKLM_AUDIO_FORMAT: str = os.getenv("NOTEBOOKLM_AUDIO_FORMAT", "deep-dive")
# Audio length: "short" | "default" | "long"
NOTEBOOKLM_AUDIO_LENGTH: str = os.getenv("NOTEBOOKLM_AUDIO_LENGTH", "default")
# Optional custom instructions for the NotebookLM hosts (leave empty for defaults)
NOTEBOOKLM_INSTRUCTIONS: str = os.getenv("NOTEBOOKLM_INSTRUCTIONS", "")
# Seconds to wait for audio generation to complete (default: 900 = 15 min)
NOTEBOOKLM_WAIT_TIMEOUT: float = float(os.getenv("NOTEBOOKLM_WAIT_TIMEOUT", "900"))
