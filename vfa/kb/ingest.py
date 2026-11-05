"""KB ingest (POC = local loaders; design §8/A20). The GitHub-webhook trigger is deferred.
Two source formats supported:
  - load_kb_markdown(): the `### Q:` / `**Keywords:**` / `**Answer:**` KB (the real source).
  - load_faqs_csv():     a simple CSV of FAQ pairs (kept as an alt example).
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

from ..schemas import KBChunk

_BOLD = re.compile(r"\*\*")
_LIST_PREFIX = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)")


def _split_csvish(cell: str, sep: str) -> list[str]:
    return [x.strip() for x in cell.split(sep) if x.strip()] if cell else []


def load_faqs_csv(path: str = "seed/faqs.csv") -> list[KBChunk]:
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(KBChunk(
                type="faq",
                question=row["question"].strip(),
                canonical_answer=row["canonical_answer"].strip(),
                topic=row.get("topic", "").strip(),
                keywords=_split_csvish(row.get("keywords", ""), "|"),
                policy_refs=_split_csvish(row.get("policy_refs", ""), "|"),
                last_reviewed_at=row.get("last_reviewed_at", "").strip(),
            ))
    return rows


def _clean_answer_line(line: str) -> str:
    line = _BOLD.sub("", line)          # drop **bold**
    line = _LIST_PREFIX.sub("", line)   # drop "- " / "1. " list markers
    return line.strip()


def load_kb_markdown(path: str = "seed/payment_faq_kb.md") -> list[KBChunk]:
    """Parse the `### Q:` KB into FAQ chunks. Non-Q/A sections (guidance notes,
    semantic tags) are ignored — they carry no question/answer pair."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    chunks: list[KBChunk] = []
    topic = ""
    question: str | None = None
    keywords: list[str] = []
    answer_parts: list[str] = []
    in_answer = False

    def flush() -> None:
        nonlocal question, keywords, answer_parts, in_answer
        if question and answer_parts:
            answer = re.sub(r"\s+", " ", " ".join(p for p in answer_parts if p)).strip()
            if answer:
                chunks.append(KBChunk(type="faq", question=question, canonical_answer=answer,
                                      topic=topic, keywords=keywords))
        question, keywords, answer_parts, in_answer = None, [], [], False

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("## Category:"):
            flush()
            topic = line.split(":", 1)[1].strip()
        elif line.startswith("## "):          # a non-Q/A section -> end any open FAQ
            flush()
            topic = ""
        elif line.startswith("### Q:"):
            flush()
            question = line.split(":", 1)[1].strip()
        elif line.startswith("**Keywords:**"):
            keywords = _split_csvish(_BOLD.sub("", line).replace("Keywords:", "", 1), ",")
        elif line.startswith("**Answer:**"):
            in_answer = True
            first = _clean_answer_line(line.replace("**Answer:**", "", 1))
            if first:
                answer_parts.append(first)
        elif line.strip() == "---":
            flush()
        elif in_answer:
            answer_parts.append(_clean_answer_line(line))

    flush()
    return chunks


def load_kb(path: str | None = None) -> list[KBChunk]:
    """Default KB loader: prefer the markdown KB, fall back to the CSV seed."""
    if path:
        return load_kb_markdown(path) if path.endswith(".md") else load_faqs_csv(path)
    md = Path("seed/payment_faq_kb.md")
    return load_kb_markdown(str(md)) if md.exists() else load_faqs_csv()
