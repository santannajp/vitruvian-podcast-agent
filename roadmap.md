# Roadmap — Content → Podcast Engine

> [!IMPORTANT]
> **Antes de implementar qualquer fase ou tarefa, consulte o `claude.md`.**
> Ele é a fonte oficial de verdade para arquitetura, convenções, interfaces e invariantes do projeto.

---

## Fase 1 — Fundação do Pipeline (MVP local funcional)

**Objetivo:** Ter um pipeline end-to-end funcionando localmente com texto simples como entrada.

> [!IMPORTANT]
> Consulte `claude.md` → seções _Core Pipeline_, _Architecture Invariants_ e _Coding Conventions_ antes de iniciar.

### Tarefas

- [ ] `input/handler.py` — Validar e normalizar entrada de texto bruto
- [ ] `markdown/converter.py` — Integrar MarkItDown para converter texto/URL/PDF em Markdown
- [ ] `language/detector.py` — Detectar idioma do conteúdo Markdown
- [ ] `script/prompts.py` — Implementar o prompt oficial do podcast (conforme `claude.md`)
- [ ] `llm/provider.py` — Definir interface `LLMProvider`
- [ ] `llm/ollama_provider.py` — Implementar provider local via Ollama
- [ ] `script/generator.py` — Gerar diálogo usando LLM e prompt oficial
- [ ] `tts/provider.py` — Definir interface `TTSProvider`
- [ ] `tts/piper_provider.py` — Implementar TTS local via Piper
- [ ] `audio/builder.py` — Combinar segmentos de áudio em MP3 final (pydub + ffmpeg)
- [ ] `app/main.py` — Orquestrar o pipeline completo de ponta a ponta

**Entrega:** Dado um texto de entrada, o sistema gera um `podcast.mp3` localmente.

---

## Fase 2 — Suporte a Conteúdo Longo

**Objetivo:** Processar documentos longos (livros, papers) com chunking e geração hierárquica.

> [!IMPORTANT]
> Consulte `claude.md` → seções _Content Chunking_ e _Hierarchical Dialogue Generation_ antes de iniciar.

### Tarefas

- [ ] `chunking/chunker.py` — Dividir Markdown em chunks respeitando cabeçalhos e limites semânticos
- [ ] `planning/dialogue_planner.py` — Gerar outline de discussão a partir dos resumos dos chunks
- [ ] `script/generator.py` — Adaptar geração para pipeline hierárquico (resumo → outline → diálogo)

**Entrega:** O sistema processa livros e papers e gera podcasts coerentes e completos.

---

## Fase 3 — Providers de API (Cloud)

**Objetivo:** Adicionar suporte a providers baseados em API como alternativa ao stack local.

> [!IMPORTANT]
> Consulte `claude.md` → seção _Provider Abstraction_ antes de iniciar. Providers não devem ser chamados fora de seus módulos.

### Tarefas

- [ ] `llm/groq_provider.py` — Implementar provider LLM via Groq
- [ ] Adicionar suporte a OpenAI como provider LLM (arquivo novo: `llm/openai_provider.py`)
- [ ] `tts/elevenlabs_provider.py` — Implementar TTS via ElevenLabs
- [ ] Criar mecanismo de seleção de provider via configuração (sem alterar o pipeline)

**Entrega:** O usuário pode escolher entre stack local (Ollama + Piper) e stack cloud (Groq/OpenAI + ElevenLabs).

---

## Fase 4 — Suporte Multilíngue Completo

**Objetivo:** Garantir que o pipeline funcione corretamente nos 5 idiomas suportados.

> [!IMPORTANT]
> Consulte `claude.md` → seções _Supported Languages_ e _Language Handling_ antes de iniciar.

### Tarefas

- [ ] Validar detecção de idioma para: `pt-BR`, `es`, `en`, `zh`, `ru`
- [ ] Garantir que o idioma detectado seja propagado em todo o pipeline
- [ ] Testar geração de diálogo e síntese de áudio em cada idioma
- [ ] Validar seleção correta de vozes TTS por idioma

**Entrega:** O sistema gera podcasts corretamente nos 5 idiomas suportados.

---

## Fase 5 — Qualidade, Testes e Documentação

**Objetivo:** Garantir confiabilidade, manutenibilidade e clareza do projeto.

> [!IMPORTANT]
> Consulte `claude.md` → seção _Coding Conventions for AI Agents_ antes de iniciar.

### Tarefas

- [x] Adicionar docstrings em todos os módulos
- [x] Escrever testes unitários para cada estágio do pipeline
- [x] Escrever testes de integração para o pipeline completo
- [x] Validar que invariantes de arquitetura do `claude.md` estão sendo respeitadas
- [x] Criar `README.md` com instruções de uso e configuração

**Entrega:** Projeto com cobertura de testes, documentado e pronto para extensão.

> **Status:** ✅ Concluída — 218 testes passando, 0 falhas.

---

## Sequência Recomendada

```
Fase 1 → Fase 2 → Fase 3 → Fase 4 → Fase 5
```

Cada fase deve ser concluída e validada antes de avançar para a próxima.

---

## Referência

| Arquivo | Função |
|---|---|
| `claude.md` | Fonte oficial de arquitetura, interfaces e convenções |
| `roadmap.md` | Plano de implementação por fases |
| `app/main.py` | Entry point do pipeline |
