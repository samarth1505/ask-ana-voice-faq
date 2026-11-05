"""Unanswered-questions report — the safe "learning loop".

Reads the shadow log and surfaces the questions the agent could NOT answer, clustered by
topic, with the nearest KB chunk it almost matched. A human reads this and decides what to
add to the KB; the next call, that question is answered. No autonomous training, no model
drift — the system only tells you what it's missing. (design: continuous KB improvement)

Run:  python -m vfa.report                       # reads ./data/shadow.sqlite
      python -m vfa.report --db data/shadow.sqlite --json
      python -m vfa.report --top 20
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass, field

from .util.text import tokenize

# outcomes that mean "we couldn't answer from the KB" (a real coverage gap)
GAP_OUTCOMES = {"escalated_floor", "escalated_grounding", "escalated_unanswerable"}
ANSWERED_OUTCOMES = {"resolved", "early_exit"}

# human-readable reason per gap outcome (what to do about it)
REASON_LABEL = {
    "escalated_floor": "nothing relevant in KB (true gap — add a new FAQ)",
    "escalated_grounding": "retrieved something close but couldn't answer safely (tighten/expand that FAQ)",
    "escalated_unanswerable": "weak match, below answerable bar (add or broaden a FAQ)",
}

# tiny stopword set just for building a cluster signature (NOT grounding)
_STOP = {"a", "an", "the", "is", "are", "do", "does", "can", "i", "my", "me", "you", "your",
         "to", "of", "for", "on", "in", "it", "how", "what", "when", "where", "why", "will",
         "and", "or", "if", "with", "this", "that", "be", "get", "am"}


@dataclass
class Cluster:
    question: str                 # representative (most common raw utterance)
    count: int
    examples: list[str] = field(default_factory=list)
    reasons: dict[str, int] = field(default_factory=dict)
    best_score: float = 0.0       # closest retrieval score seen in the cluster
    nearest_chunk_id: str | None = None  # the chunk it almost matched (None = true gap)


@dataclass
class Report:
    total_turns: int = 0
    answered: int = 0
    smalltalk: int = 0
    asked_for_human: int = 0      # escalated_explicit — not a KB gap
    unanswered: int = 0
    answer_rate: float = 0.0      # answered / (answered + unanswered), ignoring small talk/human
    clusters: list[Cluster] = field(default_factory=list)


def _signature(text: str) -> tuple[str, ...]:
    """Order-independent key of the significant tokens, so paraphrases cluster together."""
    return tuple(sorted({t for t in tokenize(text) if t not in _STOP}))


def _best(row: dict) -> tuple[float, str | None]:
    """Closest retrieval (score, chunk_id) across both paths for one turn."""
    best_s, best_id = 0.0, None
    for ids_key, sc_key in (("lexical_chunk_ids", "lexical_scores"),
                            ("semantic_chunk_ids", "semantic_scores")):
        ids = json.loads(row.get(ids_key) or "[]")
        scores = json.loads(row.get(sc_key) or "[]")
        if ids and scores and scores[0] > best_s:
            best_s, best_id = float(scores[0]), ids[0]
    return best_s, best_id


def build_report(rows: list[dict]) -> Report:
    rep = Report(total_turns=len(rows))
    by_sig: dict[tuple[str, ...], list[dict]] = {}
    for r in rows:
        outcome = r.get("outcome") or ""
        if outcome in ANSWERED_OUTCOMES:
            rep.answered += 1
        elif outcome == "smalltalk":
            rep.smalltalk += 1
        elif outcome == "escalated_explicit":
            rep.asked_for_human += 1
        elif outcome in GAP_OUTCOMES:
            rep.unanswered += 1
            by_sig.setdefault(_signature(r.get("utterance_text") or ""), []).append(r)

    denom = rep.answered + rep.unanswered
    rep.answer_rate = round(rep.answered / denom, 3) if denom else 0.0

    clusters: list[Cluster] = []
    for _sig, group in by_sig.items():
        texts = [g.get("utterance_text") or "" for g in group]
        rep_q = Counter(texts).most_common(1)[0][0]
        reasons = Counter(g.get("outcome") or "" for g in group)
        best_s, best_id = 0.0, None
        for g in group:
            s, cid = _best(g)
            if s > best_s:
                best_s, best_id = s, cid
        clusters.append(Cluster(
            question=rep_q, count=len(group),
            examples=[t for t, _ in Counter(texts).most_common(3)],
            reasons={REASON_LABEL.get(k, k): v for k, v in reasons.items()},
            best_score=round(best_s, 3), nearest_chunk_id=best_id,
        ))
    clusters.sort(key=lambda c: c.count, reverse=True)
    rep.clusters = clusters
    return rep


def load_turns(db_path: str) -> list[dict]:
    """Read all shadow rows (read-only; safe to run against a live, WAL-mode DB)."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM shadow_turns")]
    finally:
        conn.close()


def render(rep: Report, top: int = 20) -> str:
    L = ["=" * 64, "UNANSWERED-QUESTIONS REPORT  (what to add to the KB next)", "=" * 64,
         f"turns={rep.total_turns}  answered={rep.answered}  small-talk={rep.smalltalk}  "
         f"asked-for-human={rep.asked_for_human}  unanswered={rep.unanswered}",
         f"answer rate (answerable turns): {rep.answer_rate:.0%}", "-" * 64]
    if not rep.clusters:
        L.append("No unanswered questions logged yet. 🎉")
        return "\n".join(L)
    L.append(f"Top {min(top, len(rep.clusters))} gaps by volume:\n")
    for i, c in enumerate(rep.clusters[:top], 1):
        near = (f"nearest chunk {c.nearest_chunk_id} @ {c.best_score:.2f}"
                if c.nearest_chunk_id else "no close match (true gap)")
        L.append(f"{i:>2}. ×{c.count}  “{c.question}”")
        L.append(f"      {near}")
        for reason, n in c.reasons.items():
            L.append(f"      - {reason} (×{n})")
        if len(c.examples) > 1:
            L.append(f"      variants: {', '.join(repr(e) for e in c.examples[1:])}")
        L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description="Unanswered-questions report from the shadow log.")
    ap.add_argument("--db", default="./data/shadow.sqlite")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rep = build_report(load_turns(args.db))
    print(json.dumps(asdict(rep), indent=2) if args.json else render(rep, args.top))


if __name__ == "__main__":
    main()
