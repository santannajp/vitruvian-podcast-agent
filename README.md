---
title: Vitruvian Audio Agent
emoji: 🎙️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
short_description: Transforma textos, PDFs e URLs em podcasts conversacionais.
---

# Vitruvian Audio Agent — Content → Podcast Engine

Converts written content into a conversational podcast using two AI-generated voices.

Accepts URLs, PDFs, documents, or plain text as input and produces an MP3 podcast file.

---

## Pipeline

```
Input (URL / file / text)
        ↓
MarkItDown — Markdown conversion
        ↓
Language Detection
        ↓
Content Chunker (long documents only)
        ↓
Dialogue Generator (LLM)
        ↓
TTS Engine (per dialogue line)
        ↓
Podcast Builder
        ↓
podcast.mp3
```

Short documents use the direct pipeline. Long documents (books, papers) automatically use the hierarchical pipeline: chunk → summarise → outline → dialogue.

---

## Requirements

- Python 3.11+
- [ffmpeg](https://ffmpeg.org/download.html) — required by pydub for MP3 export

```bash
pip install -r requirements.txt
```

---

## Configuration

Copy `.env.example` to `.env` and fill in the required values.

```bash
cp .env.example .env
```

### Provider selection

```env
# LLM provider: ollama | groq | openai
LLM_PROVIDER=ollama

# TTS provider: piper | elevenlabs
TTS_PROVIDER=piper
```

### Ollama (local, free)

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

Start Ollama before running: `ollama serve`

### Groq (cloud, free tier)

**Obtendo a API Key:**

1. Acesse [console.groq.com](https://console.groq.com) e crie uma conta gratuita
2. No menu lateral, clique em **API Keys**
3. Clique em **Create API Key**, dê um nome e copie a chave gerada
4. O plano gratuito inclui limites generosos para uso pessoal (verifique os limites atuais em [console.groq.com/settings/limits](https://console.groq.com/settings/limits))

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama3-8b-8192
```

Modelos disponíveis no Groq (exemplos):

| Modelo | Velocidade | Qualidade |
|---|---|---|
| `llama3-8b-8192` | Muito rápido | Boa |
| `llama3-70b-8192` | Rápido | Muito boa |
| `mixtral-8x7b-32768` | Rápido | Boa, contexto longo |

---

### OpenAI (cloud)

**Obtendo a API Key:**

1. Acesse [platform.openai.com](https://platform.openai.com) e crie uma conta
2. No menu do usuário (canto superior direito), clique em **API keys**
3. Clique em **Create new secret key**, nomeie e copie a chave
4. Adicione crédito em **Settings → Billing** (a OpenAI não tem plano gratuito permanente; novos usuários podem receber créditos iniciais)

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
```

Modelos recomendados:

| Modelo | Custo | Qualidade |
|---|---|---|
| `gpt-4o-mini` | Baixo | Muito boa (recomendado) |
| `gpt-4o` | Médio | Excelente |
| `gpt-3.5-turbo` | Muito baixo | Boa |

---

### Piper TTS (local, free)

Download models from https://github.com/rhasspy/piper/releases

```env
PIPER_EXECUTABLE=piper
PIPER_MODEL_HOST1=models/pt_BR-faber-medium.onnx
PIPER_MODEL_HOST2=models/pt_BR-edresson-low.onnx
```

Per-language models (optional):

```env
PIPER_MODEL_EN_HOST1=models/en_US-lessac-medium.onnx
PIPER_MODEL_EN_HOST2=models/en_US-kusal-medium.onnx
PIPER_MODEL_ES_HOST1=models/es_ES-sharvard-medium.onnx
PIPER_MODEL_ES_HOST2=models/es_ES-sharvard-medium.onnx
PIPER_MODEL_ZH_HOST1=models/zh_CN-huayan-medium.onnx
PIPER_MODEL_ZH_HOST2=models/zh_CN-huayan-medium.onnx
PIPER_MODEL_RU_HOST1=models/ru_RU-denis-medium.onnx
PIPER_MODEL_RU_HOST2=models/ru_RU-irina-medium.onnx
```

### ElevenLabs (cloud)

**Obtendo a API Key e os Voice IDs:**

1. Acesse [elevenlabs.io](https://elevenlabs.io) e crie uma conta
2. O plano gratuito inclui 10.000 caracteres/mês — suficiente para testes
3. No menu lateral, clique em seu nome de usuário → **Profile + API key**
4. Copie a **API Key** exibida na seção *API Key*

**Obtendo os Voice IDs:**

Os Voice IDs identificam qual voz será usada para cada host. Para encontrá-los:

- **Vozes prontas (pre-built):** Acesse [elevenlabs.io/voice-library](https://elevenlabs.io/voice-library), escolha uma voz e clique em **Add to My Voices**. Em seguida, vá em **My Voices** e clique no ícone de ID ao lado da voz para copiar o Voice ID.
- **Via API:** Faça uma requisição `GET https://api.elevenlabs.io/v1/voices` com o header `xi-api-key: <sua_chave>` para listar todas as vozes e seus IDs.

Configure duas vozes distintas — uma para cada host:

```env
TTS_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your_elevenlabs_api_key
ELEVENLABS_MODEL=eleven_turbo_v2
ELEVENLABS_VOICE_HOST1=21m00Tcm4TlvDq8ikWAM   # exemplo: Rachel
ELEVENLABS_VOICE_HOST2=AZnzlk1XvdvUeBnXmlld   # exemplo: Domi
```

Modelos disponíveis:

| Modelo | Latência | Qualidade |
|---|---|---|
| `eleven_turbo_v2` | Baixa | Alta (recomendado) |
| `eleven_multilingual_v2` | Média | Máxima, multilíngue |
| `eleven_monolingual_v1` | Baixa | Alta, apenas inglês |

Per-language voice IDs (optional — falls back to defaults):

```env
ELEVENLABS_VOICE_EN_HOST1=voice_id
ELEVENLABS_VOICE_EN_HOST2=voice_id
ELEVENLABS_VOICE_ES_HOST1=voice_id
ELEVENLABS_VOICE_ES_HOST2=voice_id
ELEVENLABS_VOICE_ZH_HOST1=voice_id
ELEVENLABS_VOICE_ZH_HOST2=voice_id
ELEVENLABS_VOICE_RU_HOST1=voice_id
ELEVENLABS_VOICE_RU_HOST2=voice_id
```

### Output

```env
OUTPUT_PATH=podcast.mp3
```

### Long content thresholds

```env
# Tokens above this trigger the hierarchical pipeline
LONG_CONTENT_THRESHOLD=3000
# Max tokens per chunk (recommended: 1000–2000)
CHUNK_MAX_TOKENS=1500
```

---

## Usage

```bash
# From plain text
python app/main.py --text "Artificial intelligence is transforming the world."

# From a file (PDF, DOCX, etc.)
python app/main.py --file path/to/document.pdf

# From a URL
python app/main.py --url https://example.com/article

# Custom output path
python app/main.py --text "Content here" --output my_podcast.mp3
```

---

## Supported Languages

Language is detected automatically from the source content.

| Language | Code |
|---|---|
| Brazilian Portuguese | `pt-BR` |
| Spanish | `es` |
| English | `en` |
| Chinese | `zh` |
| Russian | `ru` |

The podcast is generated in the same language as the source content.

---

## Repository Structure

```
app/main.py               — Pipeline entry point (CLI)
input/handler.py          — Input validation and normalization
markdown/converter.py     — MarkItDown integration
language/detector.py      — Language detection
language/voices.py        — TTS voice/model mapping per language
chunking/chunker.py       — Markdown chunker for long documents
planning/dialogue_planner.py  — Chunk summarization and outline generation
script/generator.py       — Dialogue script generation
script/prompts.py         — All LLM prompt templates
llm/provider.py           — Abstract LLM interface
llm/ollama_provider.py    — Ollama (local) provider
llm/groq_provider.py      — Groq (cloud) provider
llm/openai_provider.py    — OpenAI (cloud) provider
tts/provider.py           — Abstract TTS interface
tts/piper_provider.py     — Piper (local) provider
tts/elevenlabs_provider.py — ElevenLabs (cloud) provider
audio/builder.py          — Audio assembly and MP3 export
config.py                 — Centralized configuration loader
tests/                    — Unit and integration tests
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use mocks for all external services — no API keys or local models are required to run the test suite.

---

## Architecture Invariants

The following rules are enforced and tested:

1. All content passes through Markdown conversion before any LLM call.
2. LLMs receive only Markdown or structured summaries.
3. Dialogue format always uses `Host1:` / `Host2:` prefixes.
4. Audio synthesis occurs per dialogue line.
5. Audio merging occurs only in `audio/builder.py`.
6. Providers are called only inside their own modules.
7. Detected language is propagated through every pipeline stage.
8. The output podcast language matches the detected input language.

---

## Deploy — Docker / Hugging Face Spaces

The repository ships with a production-ready `Dockerfile` (Python 3.11, multi-stage build, non-root user, Playwright + Chromium for the NotebookLM provider, ffmpeg for audio export). The image listens on port `7860`, matching the Hugging Face Spaces convention.

### Build & run locally

```bash
docker build -t vitruvian-audio .

docker run --rm -p 7860:7860 \
    -e APP_PASSWORD="$(openssl rand -hex 24)" \
    -e GROQ_API_KEY="…" \
    -e OPENAI_API_KEY="…" \
    vitruvian-audio
```

Then open `http://localhost:7860` and enter the password you generated.

### Deploy to Hugging Face Spaces (Docker SDK)

1. Create a **new Space** at <https://huggingface.co/spaces>, choosing **Docker** as the SDK and (optionally) **Private** visibility.
2. Push this repository to the Space's git remote:
   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<space-name>
   git push space main
   ```
   The YAML frontmatter at the top of this README is what tells Spaces to use Docker on port 7860.
3. In **Settings → Variables and secrets**, add the values you need as **Secrets** (never plain variables):
   - `APP_PASSWORD` — long random string. Anyone who reaches the Space URL must enter this to use the app.
   - `GROQ_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY` — only if you intend to bake the keys into the deployment. Otherwise users paste their own in the sidebar at runtime.
   - `LLM_PROVIDER`, `TTS_PROVIDER`, `PODCAST_PROVIDER` — defaults for the dropdowns.

### NotebookLM in a deployed container

NotebookLM relies on a one-time Google OAuth flow that writes `~/.notebooklm/profiles/default/storage_state.json`. A container can't open a browser for that flow, so to use NotebookLM in production you ship the session as an env var.

**One-time setup, locally:**

```bash
# Run the interactive login once on your machine
notebooklm login

# Encode the resulting session as base64 (no line wrapping)
base64 -w0 ~/.notebooklm/profiles/default/storage_state.json
```

Copy that string into the Space's Secrets as `NOTEBOOKLM_STORAGE_STATE_B64`. On startup the app decodes it into the expected path (with `0600` perms) before any NotebookLM call runs. The bootstrap is idempotent and validates the payload is JSON with a `cookies` field — invalid secrets are logged and ignored, never written to disk.

**Caveats:**

- Sessions expire. When NotebookLM rejects the cookie, the deployed app surfaces a "re-authenticate" error — you'll need to re-run `notebooklm login` locally and push a new secret.
- The Pipeline (LLM + TTS) and Transcrição modes work without this secret. Only the NotebookLM engine needs it.

### Security checklist

- ✅ `APP_PASSWORD` set as a Secret (long, random — `openssl rand -hex 24`).
- ✅ All API keys configured as **Secrets**, not Variables (Variables are visible to anyone who can read the Space).
- ✅ `.dockerignore` excludes `.env`, `.notebooklm/`, virtualenvs and generated audio — no secrets baked into the image.
- ✅ Image runs as non-root user `app` (UID 1000).
- ✅ Streamlit XSRF protection enabled, CORS disabled, usage stats opt-out.
- ✅ Password comparison uses `hmac.compare_digest` (timing-safe) with a 5-attempt cap per session.
- ⚠️ **HF Spaces is public-tunnelled by default.** Private visibility hides the *code* and *Space page* but the URL itself can still be reached by anyone with the link — `APP_PASSWORD` is your real gate.
- ⚠️ Pin `requirements.txt` versions before publishing widely; the current file uses `>=` ranges suitable for development.
