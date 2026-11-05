"""Reranker interface + offline fake + lazy real BGE cross-encoder.

Each reranked chunk's `.score` is REPLACED with the reranker's own relevance score
(normalised [0,1]) — this is a far better "does this passage answer the query" signal
than bi-encoder cosine, and the orchestrator uses the top reranked score as the
answerability gate. bge-reranker's predict() is already normalised to [0,1]. (design D7/R9)
"""
from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from ..schemas import RetrievedChunk
from ..util.text import token_set


class Reranker(Protocol):
    def rerank(self, query: str, chunks: list[RetrievedChunk], top_n: int) -> list[RetrievedChunk]: ...


class FakeReranker:
    """Offline proxy for a cross-encoder: blends retrieval score + query/text overlap."""

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_n: int = 3) -> list[RetrievedChunk]:
        q = token_set(query)

        def relevance(c: RetrievedChunk) -> float:
            overlap = len(q & token_set(c.text)) / (len(q) or 1)
            return 0.5 * c.score + 0.5 * overlap

        scored = sorted(((relevance(c), c) for c in chunks), key=lambda t: t[0], reverse=True)
        return [replace(c, score=r) for r, c in scored[:top_n]]


class BGEReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-base") -> None:
        from sentence_transformers import CrossEncoder  # lazy
        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_n: int = 3) -> list[RetrievedChunk]:
        if not chunks:
            return []
        vals = [float(x) for x in self._model.predict([(query, c.text) for c in chunks])]
        # bge-reranker-base emits [0,1]; v2-m3 emits raw logits — auto-normalise if so.
        if any(v < 0.0 or v > 1.0 for v in vals):
            import math
            vals = [1.0 / (1.0 + math.exp(-v)) for v in vals]
        scored = sorted(zip(vals, chunks), key=lambda t: t[0], reverse=True)
        return [replace(c, score=max(0.0, min(1.0, r))) for r, c in scored[:top_n]]
