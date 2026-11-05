"""In-memory retrievers — the offline stand-ins for OpenSearch (lexical) and
Qdrant/pgvector (semantic). Same `Retriever` interface, so real backends drop in later.

Lexical = surface-token overlap with a 2x boost on the FAQ `question` field
(design §8 step 3). Semantic = cosine over the embedder's vectors. Keeping them on
different signals is deliberate — it's what lets the dual paths agree *or* disagree.
"""
from __future__ import annotations

from ..embed.embedder import Embedder, FakeEmbedder, cosine
from ..schemas import KBChunk, RetrievedChunk
from ..util.text import token_set


class InMemoryLexical:
    name = "lexical"

    def __init__(self) -> None:
        self._chunks: list[KBChunk] = []
        self._q_tokens: list[set[str]] = []
        self._a_tokens: list[set[str]] = []

    def index(self, chunks: list[KBChunk]) -> None:
        self._chunks = list(chunks)
        self._q_tokens = [token_set(c.question) for c in chunks]
        self._a_tokens = [token_set(c.answer) for c in chunks]

    def _score(self, q: set[str], i: int) -> float:
        if not q:
            return 0.0
        qt, at = self._q_tokens[i], self._a_tokens[i]
        total = 0.0
        for t in q:
            if t in qt:            # question-field match (2x boost)
                total += 2.0
            elif t in at:          # answer-field match
                total += 1.0
        return total / (2.0 * len(q))   # normalise to [0,1]; exact question match -> 1.0

    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        q = token_set(query)
        scored = [
            RetrievedChunk(c.chunk_id, self._score(q, i), c.answer, c.type, c.topic,
                           c.early_exit_eligible)
            for i, c in enumerate(self._chunks)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]


class InMemoryVector:
    name = "semantic"

    def __init__(self, embedder: Embedder | None = None) -> None:
        self._embedder = embedder or FakeEmbedder()
        self._chunks: list[KBChunk] = []
        self._vecs: list[list[float]] = []

    def index(self, chunks: list[KBChunk]) -> None:
        self._chunks = list(chunks)
        # Embed the FAQ question (what callers actually ask) for FAQ chunks, else text.
        self._vecs = [
            self._embedder.embed(c.question or c.text) for c in chunks
        ]

    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        qv = self._embedder.embed(query)
        scored = [
            RetrievedChunk(c.chunk_id, cosine(qv, self._vecs[i]), c.answer, c.type, c.topic,
                           c.early_exit_eligible)
            for i, c in enumerate(self._chunks)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:k]
