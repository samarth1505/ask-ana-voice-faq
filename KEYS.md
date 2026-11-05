# API keys — what needs them, where to get them, when, and how to give them to me

## TL;DR
- **The BGE models (embedder + reranker) need NO keys** — they're free, public HuggingFace
  downloads. Same for OpenSearch, pgvector, Redis, and everything else local.
- **Only 3 tools need keys, and only later** — when we wire the real STT / LLM / TTS and make
  the agent actually talk: **Deepgram, Groq, ElevenLabs**.
- **You do NOT need to add keys yet.** Retrieval, the gate, grounding, A/B, and the shadow log
  all run with zero keys. I'll tell you the exact moment they're needed.

## Which tool needs which key

| Tool | Env var(s) in `.env` | Needed for | Cost |
|------|----------------------|------------|------|
| **Deepgram** | `DEEPGRAM_API_KEY` | real speech-to-text (voice transport / live demo) | free credit, then paid |
| **Groq** | `GROQ_API_KEY` | real LLM answer synthesis (replaces the offline fake) | free tier |
| **ElevenLabs** | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | real text-to-speech (Ask Ana voice) | paid |
| BGE embedder/reranker | — | nothing — public HF download | free |
| OpenSearch / pgvector | — | nothing — local containers | free |

## Where to fetch each
1. **Deepgram** → https://console.deepgram.com/signup → Console → **API Keys** → *Create a Key* → copy.
2. **Groq** → https://console.groq.com/ → **API Keys** → *Create API Key* → copy (shown once).
3. **ElevenLabs** → https://elevenlabs.io/ → profile menu → **API Keys** → copy. For the voice:
   open the **Voice Library**, pick an Indian-English voice, and copy its **Voice ID** into
   `ELEVENLABS_VOICE_ID`. Verify the current low-latency model name for `ELEVENLABS_MODEL_ID`.

## When to add them
Add them **right before we wire the voice loop** (the real STT→LLM→TTS adapters + transport).
I'll say explicitly "now add the 3 keys" at that step. Until then everything runs keyless.

## How to get them to me (important — do this safely)
- **Put them in the project `.env` file** (already created, and git-ignored). Open `.env` in any
  editor and paste each value after the `=`. That's the whole handoff.
- When all three are present, the app's `offline` flag flips to **False** automatically and the
  real STT/LLM/TTS adapters activate — no code change needed.
- **Do NOT paste secrets into the chat.** Chat isn't a safe channel for credentials, and I don't
  need to see the values — I only read them from `.env` at runtime. I will never print them back.
- Alternative: `export DEEPGRAM_API_KEY=... ` etc. in your shell before running. `.env` is simpler
  and persists.
