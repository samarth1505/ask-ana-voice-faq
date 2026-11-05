# Ask Ana — Voice FAQ Agent for Payments

**Ana** is a reliability-first voice FAQ agent for payment support. The first-order
constraint is **zero wrong answers**: below its grounding/answerability bar the agent
*escalates* (human callback + ticket) instead of guessing. Every spoken fact must trace
back to the retrieved knowledge base — if it can't, Ana hands off to a human.

> **Status:** offline-first core + real backends wired and verified.
> Telephony is simulated (a browser call UI drives the same per-turn pipeline); the design
> doc covers the full production plan.

---

## Why it's reliable (the design in one paragraph)

Ana never free-associates. Each turn retrieves from the KB on **two independent paths**
(lexical BM25 + semantic vectors), and will only *speak* when the answer is grounded. A
**triple-lock early-exit** serves a pre-synthesized answer when it's confident and both
retrievers agree; otherwise a **grounded LLM** drafts a reply that must pass a **grounding
guard** (every number/policy it states has to appear in the retrieved context) before it's
spoken. Anything weak, ungrounded, or explicitly asking for a person → **escalation**.

## Per-turn architecture

```
            ┌─ small-talk layer (greetings / thanks / "are you a bot?") → canned, fact-free reply
utterance ──┤
            └─ STT → dual-path retrieval (OpenSearch BM25 ‖ pgvector) → triple-lock early-exit gate
                   → rerank → grounded LLM (Groq) → grounding guard → A/B switch → TTS
                   (both candidates logged to a SQLite shadow log every turn)
```

- **Small-talk layer** (`vfa/smalltalk.py`) — a pre-retrieval conversational classifier that
  answers greetings, thanks, goodbyes, "how are you", and the "are you a bot?" identity
  question with fixed, **fact-free** lines, so chit-chat doesn't collapse into an
  escalation. It fires *only* when nothing substantive remains, so a real question
  ("hi, what are your fees?") still goes to retrieval, and "connect me to a human" still
  escalates.
- **Triple-lock gate** — serves a cached answer only when BM25 is confident **and** both
  retrievers agree **and** the chunk is a short, voice-safe FAQ (never reads card digits).
- **Grounding guard** — the LLM path's answer is rejected (→ escalate) if it states a number
  or policy that isn't in the retrieved context.
- **Shadow log** — every turn (both retrieval candidates, scores, grounding, latency) is
  written to SQLite for evaluation and the learning loop below.

## The learning loop (safe, human-in-the-loop)

Ana does **not** self-train — that would risk drift in a zero-wrong-answers system.
Instead she tells you what to add to the KB:

```bash
python -m vfa.report            # or GET /api/report while the server runs
```

The **unanswered-questions report** (`vfa/report.py`) reads the shadow log, clusters the
questions Ana couldn't answer (paraphrases group together), shows the **nearest KB chunk**
each one almost matched, and gives an answer-rate. A human writes the missing FAQ; next
call, it's answered.

## Browser voice UI

A tap-to-call web UI (`vfa/web/`, served by `vfa/server.py`) drives the real pipeline:

- **Tap "Start call"** → a ring tone + "Calling…" state while it connects, then Ana greets you.
- **Hands-free, continuous mic** with energy-based VAD and **barge-in** (just talk to interrupt).
- **Mic picker** that de-prioritizes Continuity/phone mics on macOS.
- **Live A/B switch** between retrieval paths (`auto` / `lexical` / `semantic` / kill switch).
- **Varied fillers**, pre-synthesized once at startup, played only when a turn runs slow.

```bash
VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.server   # then open http://localhost:8000
```

## Layout

- `vfa/` — the package: `retrieval/`, `embed/`, `rerank/`, `gate.py`, `grounding/`, `llm/`,
  `stt/`, `tts/`, `ab/`, `shadow/`, `orchestrator/`, `smalltalk.py`, `report.py`, `eval/`,
  `server.py`, `web/`, `factory.py`, `demo.py`, `chat.py`
- `tests/` — unit + (skippable) integration tests
- `eval/` — labeled eval set + tuned thresholds
- `seed/` — the KB (`payment_faq_kb.md`)
- `docker-compose.yml` — OpenSearch + Postgres/pgvector (local)
- `PROVISIONING.md`, `KEYS.md`, `.env.example` — setup & secrets template

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
./.venv312/bin/pip install sentence-transformers opensearch-py "psycopg[binary]" pgvector groq
VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.demo
```

### Eval harness (tune thresholds)
```bash
VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.eval.harness
```

### Voice adapters
Copy `.env.example` to `.env` (see `KEYS.md`) and fill in `DEEPGRAM_API_KEY`,
`GROQ_API_KEY`, `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`. Groq LLM is on by default;
**real TTS is opt-in** via `VFA_REAL_TTS=1` (it spends ElevenLabs credits).

## Tech stack

Python (stdlib-first core) · Deepgram (STT) · Groq `openai/gpt-oss-20b` (LLM) ·
ElevenLabs (TTS) · OpenSearch (BM25) · Postgres + pgvector · BGE-small embedder +
BGE reranker · SQLite shadow log.

## Notes

- **Secrets live in `.env` and are git-ignored — never commit real keys.** Only the empty
  `.env.example` template is tracked.
- The core is pure-stdlib (runs on Python 3.14); the real BGE/reranker models need the
  Python 3.12 venv (PyTorch wheels).
- All cloud/model backends degrade gracefully to in-memory/stdlib fakes if unavailable.
