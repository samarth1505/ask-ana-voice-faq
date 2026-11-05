"""Core data contracts (stdlib dataclasses — no pydantic, so it runs on Py 3.14)."""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

# Voice-length policy (design §11 50-word cap). An answer longer than this, or one that
# contains a card-like digit run, is NOT served verbatim on early-exit — it falls through
# to grounded LLM summarization. This protects reliability (no truncated/huge reads) and
# compliance (never read card numbers aloud — per the KB's own voice guidance).
VOICE_MAX_WORDS = 50
_CARD_DIGITS = re.compile(r"\d(?:[ -]?\d){11,18}")


def has_card_digits(text: str) -> bool:
    """True if the text contains a card/Aadhaar-like run of digits (must not be spoken)."""
    return _CARD_DIGITS.search(text) is not None


def voice_eligible(answer: str) -> bool:
    return len(answer.split()) <= VOICE_MAX_WORDS and not has_card_digits(answer)

ChunkType = Literal["faq", "policy"]
PathName = Literal["lexical", "semantic"]
Variant = Literal["lexical", "semantic", "auto", "lexical_only"]
Outcome = Literal["resolved", "early_exit", "smalltalk", "escalated_grounding", "escalated_floor",
                  "escalated_unanswerable", "escalated_explicit", "no_input"]


def chunk_id_for(text: str) -> str:
    """Content address a chunk (design §8: chunk_id = sha256 of text)."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


@dataclass
class KBChunk:
    text: str = ""
    type: ChunkType = "faq"
    topic: str = ""
    keywords: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    source_url: str = ""
    last_reviewed_at: str = ""
    # FAQ-only: the question field makes a lexical match "semantic by construction"
    question: str = ""
    canonical_answer: str = ""
    chunk_id: str = ""
    early_exit_eligible: bool = True   # computed: short + no card digits (voice-safe)

    def __post_init__(self) -> None:
        if not self.chunk_id:
            # FAQ chunks are addressed by their question+answer; policy by text.
            basis = (self.question + "\n" + self.canonical_answer) if self.type == "faq" else self.text
            self.chunk_id = chunk_id_for(basis or self.text)
        if not self.text:
            self.text = (self.question + " " + self.canonical_answer).strip()
        self.early_exit_eligible = voice_eligible(self.answer)

    @property
    def answer(self) -> str:
        return self.canonical_answer or self.text


@dataclass
class RetrievedChunk:
    chunk_id: str
    score: float          # normalised [0,1] in the in-memory scorers
    text: str
    type: ChunkType = "faq"
    topic: str = ""
    early_exit_eligible: bool = True


@dataclass
class PathResult:
    path: PathName
    retrieved: list[RetrievedChunk] = field(default_factory=list)
    candidate_response: str | None = None
    latency_ms: float = 0.0
    token_counts: dict[str, int] = field(default_factory=dict)
    cost_inr_est: float = 0.0

    @property
    def top(self) -> RetrievedChunk | None:
        return self.retrieved[0] if self.retrieved else None

    @property
    def top_score(self) -> float:
        return self.retrieved[0].score if self.retrieved else 0.0


@dataclass
class GateDecision:
    early_exit: bool
    reason: str
    chunk_id: str | None = None
    conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class GroundingResult:
    passed: bool
    flagged_claims: list[str] = field(default_factory=list)
    method: str = "regex+nli"


@dataclass
class TurnResult:
    call_id: str
    turn_id: int
    utterance: str
    served_path: str
    response: str | None
    outcome: Outcome
    active_variant: Variant
    gate: GateDecision
    grounding: dict[str, GroundingResult]      # per candidate path
    lexical: PathResult
    semantic: PathResult | None
    filler_played: bool = False
    total_latency_ms: float = 0.0
    ts: float = field(default_factory=time.time)

    def summary(self) -> str:
        tag = "EARLY-EXIT" if self.gate.early_exit else self.served_path.upper()
        return f"[{tag}] outcome={self.outcome} ({self.total_latency_ms:.0f} ms): {self.response!r}"


@dataclass
class ShadowRow:
    """One row per turn, persisted by the shadow logger (design §9)."""
    call_id: str
    turn_id: int
    ts: float
    active_variant: str
    served_path: str
    utterance_text: str
    outcome: str
    gate_early_exit: bool
    gate_reason: str
    lexical_chunk_ids: list[str]
    lexical_scores: list[float]
    lexical_candidate: str | None
    lexical_latency_ms: float
    semantic_chunk_ids: list[str]
    semantic_scores: list[float]
    semantic_candidate: str | None
    semantic_latency_ms: float
    grounding_lexical_passed: bool | None
    grounding_semantic_passed: bool | None
    total_latency_ms: float
    filler_played: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)
