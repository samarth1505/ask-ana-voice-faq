# Provisioning guide (local-first)

Scope: runs entirely on your Mac. Telephony is **simulated** (mic /
browser WebRTC) — no inbound, no real outbound, no tunnel. Everything production-scoped is
removed or deferred (see the design doc). You need **three cloud sign-ups**; the rest is local.

---

## The 3 sign-ups (fill these in `.env`)

### 1. Deepgram — STT  [free credit]
- https://console.deepgram.com/signup → Console → **API Keys**.
- Put it in `DEEPGRAM_API_KEY`. Free credit on signup; no money up front.

### 2. Groq — LLM  [free tier]
- https://console.groq.com/ → **API Keys**.
- Put it in `GROQ_API_KEY`. Free tier is rate-limited (fine to start).

### 3. ElevenLabs — TTS  [PAID]
- https://elevenlabs.io/ → Profile → **API Key** → `ELEVENLABS_API_KEY`.
- Browse the **Voice Library**, pick an Indian-English voice, copy its id → `ELEVENLABS_VOICE_ID`.
- `ELEVENLABS_MODEL_ID` defaults to a low-latency turbo model — **verify the current name** on
  their docs; it changes.
- This is the one that costs money. (If you'd rather not pay yet, say so and I'll
  swap in local **Piper** TTS for zero cost.)

---

## Local stack (no sign-up — I run these for you)

Two containers via Docker Desktop:
```bash
docker compose up -d
```
- **OpenSearch** (BM25 lexical retrieval) on `localhost:9200`
- **Postgres + pgvector** (vectors + KB metadata) on `localhost:5432`

Plus, in-process (Python, local model downloads, no key): the embedder (BGE-small),
reranker (BGE-reranker-v2), and grounding NLI. Audio + transcripts go to `./data/` on disk
(replacing Cloudflare R2). The shadow log is a local SQLite file.

---

## Removed / deferred (confirmed)

**Removed:** inbound PSTN, Oracle/Fly hosting, Cloudflare R2, GitHub webhook ingest (replaced
by a local `ingest.py`).
**Deferred:** Exotel/real telephony, Freshdesk ticketing (escalation → local log row),
Langfuse + Grafana dashboards, nightly eval harness, sentiment/repeat classifier, speculative
filler, Postgres drain of the shadow log, LiveKit Cloud.

The core loop and all the novel bets stay: dual-path shadow A/B, triple-lock early exit,
pre-synth audio cache, grounding guard.

---

## "Environment ready" = these steps done
1. Scaffold files exist ✅ (`.gitignore`, `.env.example`, `.env`, `docker-compose.yml`, this file).
2. You fill the 3 keys in `.env`.
3. `docker compose up -d` brings up OpenSearch + Postgres (I'll run + verify this).
4. I run a connectivity check on Deepgram / Groq / ElevenLabs (auth ping — ElevenLabs check
   uses a zero-cost metadata endpoint, not synthesis) and report ✅/❌ per service.
