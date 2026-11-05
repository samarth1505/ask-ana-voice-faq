# Voice FAQ Agent for Payments — POC

A reliability-first voice FAQ agent for payment support. **Zero wrong answers** is the
first-order constraint: below its confidence/answerability bar the agent escalates
(human callback + ticket) instead of guessing.

> Status: proof-of-concept. Offline-first core + real backends wired and verified.
> Telephony is simulated (text-driven) in the POC; see the design doc for the full plan.

## Per-turn architecture
```
STT → dual-path retrieval (OpenSearch BM25 ‖ pgvector) → triple-lock early-exit gate
    → rerank → grounded LLM (Groq) → grounding guard → A/B switch → TTS
    (both candidates logged to a SQLite shadow log every turn)
```
The gate serves a pre-synth answer only when BM25 is confident **and** both retrievers
agree **and** the chunk is a short, voice-safe FAQ. Otherwise it falls through to the LLM
path, whose answer must pass the grounding guard; a weak reranker score or a grounding
failure escalates rather than speaks.

## Layout
- `vfa/` — the package: `retrieval/`, `embed/`, `rerank/`, `gate.py`, `grounding/`,
  `llm/`, `stt/`, `tts/`, `ab/`, `shadow/`, `orchestrator/`, `eval/`, `factory.py`, `demo.py`
- `tests/` — unit + (skippable) integration tests
- `eval/` — labeled eval set + tuned thresholds
- `seed/` — the KB (`payment_faq_kb.md`)
- `docker-compose.yml` — OpenSearch + Postgres/pgvector (local)
- `PROVISIONING.md`, `KEYS.md`, `.env.example` — setup & secrets

## Run it

### Offline (no keys, no Docker) — Python 3.11+
```bash
python3 -m vfa.demo
python3 -m unittest discover -s tests
```

### Real backends + real models — Docker + Python 3.12
```bash
docker compose up -d                         # OpenSearch + pgvector
python3.12 -m venv .venv312
./.venv312/bin/pip install sentence-transformers opensearch-py "psycopg[binary]" pgvector
VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.demo
```

### Eval harness (tune thresholds)
```bash
VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.eval.harness
```

### Voice adapters
Put keys in `.env` (see `KEYS.md`): `DEEPGRAM_API_KEY`, `GROQ_API_KEY`,
`ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`. Groq LLM is on by default; **real TTS is
opt-in** via `VFA_REAL_TTS=1` (it spends ElevenLabs credits).

## Notes
- Secrets live in `.env` and are **git-ignored**. Never commit real keys.
- The core is pure-stdlib (runs on Python 3.14); the real BGE/reranker models need the
  Python 3.12 venv (PyTorch wheels).
- All cloud/model backends degrade gracefully to in-memory/stdlib fakes if unavailable.
