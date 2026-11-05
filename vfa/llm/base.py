"""LLM synthesizer interface + offline fakes.

Offline fake composes the answer ONLY from retrieved chunk text (grounded by
construction), so the grounding guard passes. Real Groq/Gemini adapters implement the
same interface and switch on when keys exist. (design R12/D8)
"""
from __future__ import annotations

from typing import Protocol

from ..schemas import RetrievedChunk


def _cap_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    clipped = " ".join(words[:max_words])
    # prefer ending at the last sentence boundary so we never emit a mid-sentence fragment
    cut = max(clipped.rfind(". "), clipped.rfind("! "), clipped.rfind("? "))
    if cut >= 40:
        return clipped[:cut + 1]
    return clipped.rstrip(",.;:") + "."


class Synthesizer(Protocol):
    def synthesize(self, utterance: str, chunks: list[RetrievedChunk], max_words: int) -> str: ...


class FakeSynthesizer:
    """Grounded-by-construction: answers with the top chunk's text, length-capped."""

    def synthesize(self, utterance: str, chunks: list[RetrievedChunk], max_words: int = 50) -> str:
        if not chunks:
            return ""
        return _cap_words(chunks[0].text.strip(), max_words)


class FabricatingSynthesizer:
    """TEST-ONLY: injects an ungrounded number so the grounding guard must FAIL."""

    def synthesize(self, utterance: str, chunks: list[RetrievedChunk], max_words: int = 50) -> str:
        base = chunks[0].text.strip() if chunks else "Your refund"
        return _cap_words(base + " It will arrive in exactly 99 business days.", max_words)
