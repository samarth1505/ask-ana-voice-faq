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
        """LLM-first routing. The triple-lock early-exit already serves confident cache hits
        before the router runs, so everything that reaches here should go to the semantic
        (LLM) path to get a grounded answer — routing it to the lexical-only arm just bails on
        a weak BM25 score and over-escalates. The lexical arm stays reachable via variant=lexical."""
        return "semantic"
