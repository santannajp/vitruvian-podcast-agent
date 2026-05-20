# CLAUDE.md

# Project: Content → Podcast Engine

## Project Overview

This project converts written content into a conversational podcast using two AI-generated voices.

The system accepts many input types (links, PDFs, documents, raw text) and converts them into Markdown using **MarkItDown**. The Markdown is then processed by a language model that generates a natural conversation between two hosts. Finally, a text-to-speech engine synthesizes the conversation into a podcast audio file.

The architecture is designed as a **modular, deterministic pipeline** capable of scaling to very long documents such as books and research papers.

The long-term goal is to build a **general-purpose engine that transforms written knowledge into engaging conversational audio**.

---

# Core Pipeline

The system follows a deterministic pipeline:

```text
Input → Markdown Conversion → Language Detection → Content Chunking → Dialogue Generation → Audio Synthesis → Podcast Output
```

Architecture diagram:

```text
Input (URL / file / text)
        ↓
MarkItDown
        ↓
Markdown content
        ↓
Language Detection
        ↓
Content Chunker
        ↓
Dialogue Planner
        ↓
Dialogue Generator (LLM)
        ↓
Dialogue Script
        ↓
TTS Engine
        ↓
Audio Segments
        ↓
Podcast Builder
        ↓
Final MP3
```

Each stage must produce a well-defined output that becomes the input for the next stage.

---

# Supported Languages

The system must support at least the following languages:

* Brazilian Portuguese
* Spanish
* English
* Chinese
* Russian

Language codes:

```text
pt-BR
es
en
zh
ru
```

The podcast must be generated **in the same language as the source content by default**.

Translation may be supported in future versions.

---

# Language Handling

Language detection occurs after Markdown conversion.

Example flow:

```text
markdown_text
      ↓
language_detector
      ↓
language_code
```

Example output:

```text
DetectedLanguage:
    code: pt-BR
```

The detected language must be propagated through the entire pipeline.

---

# Architecture Principles

## 1. Modular Pipeline

Each stage of the system must be implemented as an independent module.

Modules communicate only through structured outputs.

No module should depend on implementation details of another module.

---

## 2. Provider Abstraction

External services must be abstracted behind provider interfaces.

This allows switching between:

Fully free / local stack

* Ollama (LLM)
* Piper TTS

API-based stack with free tiers

* Groq
* OpenAI
* ElevenLabs

Provider switching must not require modifications to the core pipeline.

---

## 3. Single Internal Representation

All content must be converted to **Markdown** before LLM processing.

Markdown is the canonical internal format because it:

* preserves structure
* is token efficient
* is highly compatible with LLMs

---

## 4. Deterministic Pipeline

Each pipeline stage must produce predictable outputs.

Stage outputs:

```text
MarkdownConverter → markdown_text
LanguageDetector → language_code
Chunker → content_chunks
DialoguePlanner → dialogue_outline
ScriptGenerator → dialogue_script
TTSProvider → audio_segments
PodcastBuilder → final_mp3
```

---

# Architecture Invariants

The following rules must **never be violated**:

1. All content must pass through Markdown conversion.

2. LLMs must only receive Markdown or structured summaries.

3. Dialogue format must always follow:

```text
Host1:
Host2:
```

4. Audio generation must occur per dialogue line.

5. Audio merging must occur only in the Podcast Builder.

6. Providers must never be called outside provider modules.

7. The detected language must always be propagated.

8. The output podcast language must match the detected language.

---

# Handling Long Content

Long documents such as books or research papers require special handling.

The system must use **content chunking and hierarchical dialogue generation**.

---

# Content Chunking

Large Markdown documents must be divided into logical segments.

Chunking should prioritize:

* section headings
* chapter boundaries
* semantic coherence

Example:

```text
Full Markdown
      ↓
Chunker
      ↓
Chunk 1
Chunk 2
Chunk 3
```

Each chunk must stay within the token limits of the LLM.

Recommended chunk size:

```text
1000–2000 tokens
```

---

# Hierarchical Dialogue Generation

Dialogue generation should occur in multiple stages.

## Stage 1 — Content Summarization

Each chunk is summarized independently.

Output:

```text
chunk_summary
```

---

## Stage 2 — Episode Outline Generation

Chunk summaries are combined to generate a structured discussion plan.

Example:

```text
Podcast Outline

1. Introduction
2. Main idea
3. Supporting arguments
4. Examples
5. Conclusion
```

---

## Stage 3 — Dialogue Generation

The LLM generates the final conversation using:

* chunk summaries
* discussion outline
* original Markdown context

This approach produces more natural and coherent conversations.

---

# Core Components

## Input Layer

Handles user inputs.

Supported inputs:

* URLs
* PDFs
* documents
* raw text

Responsibilities:

* validate input
* pass content to Markdown conversion

Output:

```text
InputContent:
    source_type
    source_value
```

---

## Markdown Conversion

Library used:

MarkItDown

Responsibilities:

* convert all inputs into Markdown
* preserve structure such as headings, lists, tables, and links

Output:

```text
markdown_text
```

---

## Language Detection

Detects the language of the Markdown content.

Recommended libraries:

* langdetect
* fastText

Output:

```text
language_code
```

---

## Content Chunker

Divides large Markdown documents into smaller segments.

Responsibilities:

* respect section boundaries
* maintain semantic coherence
* produce chunks suitable for LLM input

Output:

```text
content_chunks
```

---

## Dialogue Planner

Generates a discussion outline from chunk summaries.

Responsibilities:

* identify main themes
* create logical flow for conversation
* avoid redundancy

Output:

```text
dialogue_outline
```

---

## Script Generator

Generates the final podcast dialogue.

Output format:

```text
Host1: dialogue
Host2: dialogue
Host1: dialogue
Host2: dialogue
```

Dialogue must:

* remain faithful to the source content
* feel natural and conversational
* alternate between hosts

---

# Official Podcast Prompt

The following base prompt must be used.

```text
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

Output format:

Host1: ...
Host2: ...
Host1: ...
Host2: ...

Content:
{content}
```

Prompts must be stored separately from code.

---

# LLM Providers

Interface:

```python
class LLMProvider:
    def generate_script(markdown: str, language: str) -> str
```

Possible implementations:

Local providers:

* Ollama

API providers:

* Groq
* OpenAI

Providers must support multilingual output.

---

# Text-to-Speech

Responsible for converting dialogue into audio.

Interface:

```python
class TTSProvider:
    def synthesize(text: str, voice: str, language: str)
```

Voices:

```text
Host1 → voice_a
Host2 → voice_b
```

Possible providers:

Free / local:

* Piper TTS

API providers:

* ElevenLabs

---

# Podcast Builder

Combines audio segments into the final podcast.

Responsibilities:

* maintain dialogue order
* insert pauses between speakers
* export MP3

Recommended tools:

* pydub
* ffmpeg

Output:

```text
podcast.mp3
```

---

# Repository Structure

```text
podcast-engine/

input/
    handler.py

markdown/
    converter.py

language/
    detector.py

chunking/
    chunker.py

planning/
    dialogue_planner.py

llm/
    provider.py
    ollama_provider.py
    groq_provider.py

script/
    generator.py
    prompts.py

tts/
    provider.py
    piper_provider.py
    elevenlabs_provider.py

audio/
    builder.py

app/
    main.py
```

---

# Coding Conventions for AI Agents

1. Functions must be small and focused.

2. Avoid monolithic modules.

3. Separate business logic from infrastructure.

4. Prompts must never be embedded in functions.

5. Use provider interfaces consistently.

6. All modules must include docstrings.

7. Prefer readability over cleverness.

8. Avoid premature optimization.

---

# Future Extensions

Planned capabilities:

Multi-episode generation:

```text
Book
 ↓
Chapter detection
 ↓
Episode scripts
 ↓
Podcast series
```

Additional future features:

* configurable host personalities
* different conversation styles
* multiple hosts
* podcast length control
* multilingual translation mode
* content recommendation
* automatic podcast titles and descriptions

---

# Long-Term Vision

The system should evolve into a **general-purpose engine that converts written knowledge into conversational audio**.

Target content types:

* articles
* books
* research papers
* newsletters
* threads
* documentation

The goal is to make complex information more accessible through engaging podcast-style conversations.
