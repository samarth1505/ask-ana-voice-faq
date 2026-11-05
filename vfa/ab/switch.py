"""A/B switch — R2-internal serve-selection logic (design §9/R14).

Picks WHICH candidate reaches TTS given the active variant. Both retrieval paths still
run every turn (for the shadow log); only `lexical_only` actually skips the semantic path
(load-shedding). `auto` uses a zero-cost rule router (no LLM call). (design D12, auto=rule-based)
"""
from __future__ import annotations

from ..config import Settings
from ..schemas import PathResult

_QUESTION_WORDS = {"what", "when", "where", "which", "how", "who", "is", "are", "do", "does", "can"}


class ABSwitch:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self.variant = settings.ab_variant

    @property
    def skip_semantic(self) -> bool:
        return self.variant == "lexical_only"

    def select(self, utterance: str, lexical: PathResult, semantic: PathResult | None) -> str:
        if self.variant in ("lexical", "lexical_only"):
            return "lexical"
        if self.variant == "semantic":
            return "semantic"
        return self._route(utterance, lexical, semantic)

    def _route(self, utterance: str, lexical: PathResult, semantic: PathResult | None) -> str:
        """Rule router: short/keyword-y queries with a confident, well-separated BM25 hit
        go lexical; descriptive/ambiguous go semantic."""
        top = lexical.top_score
        margin = (lexical.retrieved[0].score - lexical.retrieved[1].score) \
            if len(lexical.retrieved) > 1 else top
        words = utterance.strip().lower().split()
        starts_with_qword = bool(words) and words[0] in _QUESTION_WORDS
        short = len(words) <= 6
        if top >= self._s.tau_bm25 and margin >= 0.10 and (short or starts_with_qword):
            return "lexical"
        return "semantic"
