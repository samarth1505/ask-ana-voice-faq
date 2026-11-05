"""Real Groq synthesizer via the official SDK. Grounded but agentic: answers paraphrased /
edge-case questions from the retrieved context, states only facts that come from it, and
replies INSUFFICIENT_CONTEXT only when the context truly doesn't address the question.

Errors are logged (not silently swallowed) and return "" so the orchestrator escalates —
a visible, fail-safe degrade. (design R12/D8)
"""
from __future__ import annotations

import logging

from ..schemas import RetrievedChunk

log = logging.getLogger("vfa.groq")

SYSTEM_PROMPT = (
    "You are Priya, a warm, concise payments support agent on a phone call. "
    "Use ONLY the information in the context below to help the caller. Be helpful: if the "
    "context contains anything relevant — even a partial or adjacent answer, or a different "
    "wording of the same thing — answer with what you can, naturally and confidently. "
    "Every specific fact you state (numbers, timeframes, percentages, policy names) MUST come "
    "from the context; never invent one, and don't state a number the context doesn't give. "
    "ONLY reply with exactly INSUFFICIENT_CONTEXT when the context is about an entirely "
    "different topic from what the caller asked (e.g. they ask about something unrelated to "
    "payments). Keep it under {max_words} words, friendly and conversational for speech — no "
    "lists, no markdown."
)


class GroqSynthesizer:
    SENTINEL = "INSUFFICIENT_CONTEXT"

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-20b", timeout_ms: int = 8000) -> None:
        from groq import Groq  # lazy; only needed in real mode
        self._client = Groq(api_key=api_key, timeout=timeout_ms / 1000.0, max_retries=0)
        self._model = model

    def synthesize(self, utterance: str, chunks: list[RetrievedChunk], max_words: int = 50) -> str:
        context = "\n\n".join(f"- {c.text}" for c in chunks)
        # gpt-oss / qwen are REASONING models: without this they burn the token budget on
        # hidden reasoning and return empty content (-> false escalation). "low" keeps them
        # fast and leaves room for the actual answer.
        extra = {"reasoning_effort": "low"} if ("gpt-oss" in self._model or "qwen" in self._model) else {}
        try:
            resp = self._client.chat.completions.create(
                model=self._model, temperature=0.3, max_tokens=400,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT.format(max_words=max_words)},
                    {"role": "user", "content": f"Context:\n{context}\n\nCaller asked: {utterance}"},
                ],
                **extra,
            )
            text = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            log.warning("Groq call failed: %s", e)   # visible, not swallowed
            return ""
        return "" if (not text or text.strip() == self.SENTINEL) else text
