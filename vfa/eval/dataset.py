"""Load the labeled eval set and resolve each `expected` marker to a KB chunk_id.

Each line of evalset.jsonl is {"utterance", "expected"} where `expected` is either the
literal "ESCALATE" (the turn SHOULD escalate — out-of-KB / account-specific / human
request) or a unique substring of exactly one KB question (the gold chunk to serve).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..schemas import KBChunk


@dataclass
class EvalExample:
    utterance: str
    gold_chunk_id: str | None   # None => should escalate
    marker: str
    note: str = ""

    @property
    def should_escalate(self) -> bool:
        return self.gold_chunk_id is None


def resolve_marker(marker: str, chunks: list[KBChunk]) -> str:
    m = marker.lower()
    matches = [c for c in chunks if m in c.question.lower()]
    if len(matches) != 1:
        raise ValueError(f"marker {marker!r} resolved to {len(matches)} chunks (need exactly 1)")
    return matches[0].chunk_id


def load_evalset(chunks: list[KBChunk], path: str = "eval/evalset.jsonl") -> list[EvalExample]:
    out: list[EvalExample] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec["expected"] == "ESCALATE":
            out.append(EvalExample(rec["utterance"], None, "ESCALATE", rec.get("note", "")))
        else:
            cid = resolve_marker(rec["expected"], chunks)
            out.append(EvalExample(rec["utterance"], cid, rec["expected"], rec.get("note", "")))
    return out
