"""Real Groq synthesizer (stdlib urllib — no extra deps). Grounded-only prompt; any
error/timeout returns "" so the orchestrator escalates rather than speaks (fail-safe). (R12)

Timeout note: the design's 600 ms hard SLO is a production latency target (covered by the
speculative filler). For POC functional correctness this adapter uses a generous timeout;
the SLO is enforced at the orchestrator/transport layer, not here.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from ..schemas import RetrievedChunk

SYSTEM_PROMPT = (
    "You are Priya, a payments support assistant. Answer ONLY using the provided context. "
    "Every number, policy name, and entity in your answer MUST appear in the context. "
    "If the context does not contain the answer, reply exactly: INSUFFICIENT_CONTEXT. "
    "Keep the answer under {max_words} words, warm and natural for speech."
)


class GroqSynthesizer:
    SENTINEL = "INSUFFICIENT_CONTEXT"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile",
                 timeout_ms: int = 8000) -> None:
        self._key = api_key
        self._model = model
        self._timeout = timeout_ms / 1000.0

    def synthesize(self, utterance: str, chunks: list[RetrievedChunk], max_words: int = 50) -> str:
        context = "\n\n".join(f"[{c.chunk_id}] {c.text}" for c in chunks)
        body = json.dumps({
            "model": self._model,
            "temperature": 0.2,
            "max_tokens": 160,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(max_words=max_words)},
                {"role": "user", "content": f"Context:\n{context}\n\nCaller asked: {utterance}"},
            ],
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions", data=body, method="POST",
            headers={"Authorization": f"Bearer {self._key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as r:
                data = json.loads(r.read())
            text = data["choices"][0]["message"]["content"].strip()
        except Exception:
            return ""   # fail-safe: empty -> orchestrator runs the callback/escalation flow
        return "" if self.SENTINEL in text else text
