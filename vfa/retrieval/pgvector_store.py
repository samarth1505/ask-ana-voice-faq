"""pgvector semantic retriever (design §6/§8/R8/D6). Stores the embedder's vectors in
Postgres and ranks by cosine. Uses the SAME embedder as query time (one model, index and
query). In the POC that's the 256-d FakeEmbedder — no ML wheels — so this exercises the
real DB path while staying offline-safe.
"""
from __future__ import annotations

from ..embed.embedder import Embedder, FakeEmbedder
from ..schemas import KBChunk, RetrievedChunk

_TABLE = "kb_vectors"


class PgVectorSemantic:
    name = "semantic"

    def __init__(self, dsn: str, embedder: Embedder | None = None, timeout: float = 3.0,
                 table: str = _TABLE) -> None:
        import psycopg  # lazy
        self._embedder = embedder or FakeEmbedder()
        self._dim = self._embedder.dim
        self._table = table
        self._conn = psycopg.connect(dsn, connect_timeout=int(timeout))
        self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        self._conn.commit()

    @staticmethod
    def _lit(vec: list[float]) -> str:
        """pgvector literal: '[0.1,0.2,...]' — avoids numpy / register_vector."""
        return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"

    def health(self) -> bool:
        try:
            self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def index(self, chunks: list[KBChunk]) -> None:
        self._conn.execute(f"DROP TABLE IF EXISTS {self._table}")
        self._conn.execute(
            f"CREATE TABLE {self._table} ("
            " chunk_id TEXT PRIMARY KEY, type TEXT, topic TEXT, answer TEXT,"
            " early_exit_eligible BOOLEAN, embedding vector(%s))" % self._dim
        )
        with self._conn.cursor() as cur:
            for c in chunks:
                vec = self._lit(self._embedder.embed(c.question or c.text))
                cur.execute(
                    f"INSERT INTO {self._table} VALUES (%s,%s,%s,%s,%s,%s::vector)",
                    (c.chunk_id, c.type, c.topic, c.answer, c.early_exit_eligible, vec),
                )
        self._conn.commit()

    def search(self, query: str, k: int = 5) -> list[RetrievedChunk]:
        qv = self._lit(self._embedder.embed(query))
        rows = self._conn.execute(
            f"SELECT chunk_id, type, topic, answer, early_exit_eligible,"
            f" 1 - (embedding <=> %s::vector) AS sim FROM {self._table}"
            f" ORDER BY embedding <=> %s::vector LIMIT %s",
            (qv, qv, k),
        ).fetchall()
        return [
            RetrievedChunk(chunk_id=r[0], score=max(0.0, float(r[5])), text=r[3],
                           type=r[1], topic=r[2], early_exit_eligible=r[4])
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
