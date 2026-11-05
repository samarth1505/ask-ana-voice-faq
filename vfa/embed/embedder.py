"""Embedder interface + a deterministic offline fake + a lazy real BGE adapter.

The fake produces a normalised bag-of-(tokens + char-trigrams) vector so that
*paraphrases* score higher than pure surface-token overlap — i.e. a genuinely
different signal from the lexical path, which is what makes the dual-path A/B and
the triple-lock "agreement" check meaningful in the POC. (design D4/R6)
"""
from __future__ import annotations

import hashlib
import math
from typing import Protocol

from ..util.text import normalize, tokenize


class Embedder(Protocol):
    dim: int
    def embed(self, text: str) -> list[float]: ...


def _hash_idx(token: str, dim: int) -> int:
    return int(hashlib.md5(token.encode()).hexdigest(), 16) % dim


def _trigrams(norm_text: str) -> list[str]:
    s = f" {norm_text} "
    return [s[i:i + 3] for i in range(len(s) - 2)]


class FakeEmbedder:
    """Offline, deterministic, dependency-free embedder."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        norm = normalize(text)
        for tok in tokenize(text):
            vec[_hash_idx("tok:" + tok, self.dim)] += 1.0
        for tri in _trigrams(norm):
            vec[_hash_idx("tri:" + tri, self.dim)] += 0.5
        n = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / n for v in vec]


class BGELocalEmbedder:
    """Real local embedder (lazy import — only when wiring models on a 3.12 venv)."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from sentence_transformers import SentenceTransformer  # lazy
        self._model = SentenceTransformer(model_name)
        self.dim = (self._model.get_embedding_dimension()
                    if hasattr(self._model, "get_embedding_dimension")
                    else self._model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()


def cosine(a: list[float], b: list[float]) -> float:
    """Dot product; both inputs are L2-normalised, features non-negative -> [0,1]."""
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b))))
