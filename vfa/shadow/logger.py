"""Shadow logger (design §9/A18). POC = local SQLite (WAL mode), one row per turn,
BOTH candidates logged regardless of who served. Postgres drain is deferred for the POC.

Writes are non-blocking in spirit (SQLite WAL ~1 ms); the orchestrator calls this after
the turn is served so it never sits on the response path.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..schemas import ShadowRow

_SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_turns (
    call_id TEXT, turn_id INTEGER, ts REAL,
    active_variant TEXT, served_path TEXT,
    utterance_text TEXT, outcome TEXT,
    gate_early_exit INTEGER, gate_reason TEXT,
    lexical_chunk_ids TEXT, lexical_scores TEXT, lexical_candidate TEXT, lexical_latency_ms REAL,
    semantic_chunk_ids TEXT, semantic_scores TEXT, semantic_candidate TEXT, semantic_latency_ms REAL,
    grounding_lexical_passed INTEGER, grounding_semantic_passed INTEGER,
    total_latency_ms REAL, filler_played INTEGER,
    PRIMARY KEY (call_id, turn_id)
);
"""


class ShadowLogger:
    def __init__(self, db_path: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def write(self, row: ShadowRow) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO shadow_turns VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row.call_id, row.turn_id, row.ts, row.active_variant, row.served_path,
                row.utterance_text, row.outcome,
                int(row.gate_early_exit), row.gate_reason,
                json.dumps(row.lexical_chunk_ids), json.dumps(row.lexical_scores),
                row.lexical_candidate, row.lexical_latency_ms,
                json.dumps(row.semantic_chunk_ids), json.dumps(row.semantic_scores),
                row.semantic_candidate, row.semantic_latency_ms,
                _tri(row.grounding_lexical_passed), _tri(row.grounding_semantic_passed),
                row.total_latency_ms, int(row.filler_played),
            ),
        )
        self._conn.commit()

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM shadow_turns").fetchone()[0]

    def close(self) -> None:
        self._conn.close()


def _tri(v: bool | None) -> int | None:
    return None if v is None else int(v)
