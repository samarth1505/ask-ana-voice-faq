"""Retriever interface shared by in-memory (POC), OpenSearch, and pgvector backends."""
from __future__ import annotations

from typing import Protocol

from ..schemas import KBChunk, RetrievedChunk


class Retriever(Protocol):
    name: str
    def index(self, chunks: list[KBChunk]) -> None: ...
    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]: ...
