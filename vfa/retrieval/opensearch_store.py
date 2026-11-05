"""OpenSearch lexical retriever (design §6/§8/R7). BM25 with an Indian-English analyzer
(lowercase + asciifolding + synonyms) and a 2x boost on the FAQ `question` field.

BM25 scores are unbounded, but the gate works on a normalised [0,1] score, so we squash
with s/(s+K). K is a per-corpus tuning dial — it sets where "a good match" lands relative
to tau_bm25, and MUST be fit on the eval set before trusting early-exit. (flagged, design R10)
"""
from __future__ import annotations

from ..schemas import KBChunk, RetrievedChunk
from ..util.text import SYNONYMS

_INDEX = "vfa_faq"


def _synonym_lines() -> list[str]:
    # "unified payments interface, upi"  (Solr/OpenSearch synonym format)
    return [f"{long}, {short}" for long, short in SYNONYMS.items()]


class OpenSearchLexical:
    name = "lexical"

    def __init__(self, url: str, score_k: float = 8.0, timeout: float = 3.0,
                 index: str = _INDEX) -> None:
        from opensearchpy import OpenSearch  # lazy
        self._score_k = score_k
        self._index = index
        self._client = OpenSearch(hosts=[url], http_compress=True, timeout=timeout,
                                  max_retries=1, retry_on_timeout=False)  # noqa: E501

    def health(self) -> bool:
        try:
            return bool(self._client.ping())
        except Exception:
            return False

    def index(self, chunks: list[KBChunk]) -> None:
        if self._client.indices.exists(index=self._index):
            self._client.indices.delete(index=self._index)
        self._client.indices.create(index=self._index, body={
            "settings": {
                "analysis": {
                    "filter": {"vfa_syn": {"type": "synonym", "synonyms": _synonym_lines()}},
                    "analyzer": {"vfa_en": {
                        "tokenizer": "standard",
                        "filter": ["lowercase", "asciifolding", "vfa_syn"],
                    }},
                }
            },
            "mappings": {"properties": {
                "chunk_id": {"type": "keyword"},
                "question": {"type": "text", "analyzer": "vfa_en"},
                "answer": {"type": "text", "analyzer": "vfa_en"},
                "type": {"type": "keyword"},
                "topic": {"type": "keyword"},
                "early_exit_eligible": {"type": "boolean"},
            }},
        })
        for c in chunks:
            self._client.index(index=self._index, id=c.chunk_id, body={
                "chunk_id": c.chunk_id, "question": c.question, "answer": c.answer,
                "type": c.type, "topic": c.topic, "early_exit_eligible": c.early_exit_eligible,
            })
        self._client.indices.refresh(index=self._index)

    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        res = self._client.search(index=self._index, body={
            "size": k,
            "query": {"multi_match": {
                "query": query,
                "fields": ["question^2", "answer"],   # 2x boost on the question field
                "type": "best_fields",
            }},
        })
        out = []
        for hit in res["hits"]["hits"]:
            raw = float(hit["_score"])
            norm = raw / (raw + self._score_k)        # unbounded BM25 -> [0,1)
            src = hit["_source"]
            out.append(RetrievedChunk(
                chunk_id=src["chunk_id"], score=norm, text=src["answer"],
                type=src.get("type", "faq"), topic=src.get("topic", ""),
                early_exit_eligible=src.get("early_exit_eligible", True),
            ))
        return out
