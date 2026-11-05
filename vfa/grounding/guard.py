"""Grounding guard (design §6/§8/R13): the sole authority that makes an LLM candidate
speakable. Returns hard pass/fail; the orchestrator (not the guard) runs escalation.

Method = deterministic regex matching:
  - every numeric/quantitative claim in the response must appear in retrieved context
  - every known payment entity named in the response must appear in context
Any miss -> FAIL (hard; no retry, no templated guess).

⚠️ RELIABILITY GAP (flagged): regex alone catches *fabricated numbers/entities* but can
miss a *paraphrased* false claim that invents no new number. The real build adds the NLI
entailment pass (DeBERTa/MiniLM) here via the `nli` hook; offline it is None, so the guard
is conservative-but-incomplete. Phase-2 gate measures recall on the red-team set. (design D9)
"""
from __future__ import annotations

from typing import Protocol

from ..schemas import GroundingResult, RetrievedChunk
from ..util.text import claim_in_context, extract_claims, normalize

# Known payment entities a response might assert; each must trace to context.
ENTITIES = [
    "upi", "neft", "rtgs", "imps", "rupay", "visa", "mastercard", "autopay",
    "mandate", "wallet", "sms", "otp", "mdr", "chargeback", "settlement",
]


class NLI(Protocol):
    def entails(self, premise: str, hypothesis: str) -> bool: ...


class GroundingGuard:
    def __init__(self, nli: NLI | None = None) -> None:
        self._nli = nli

    def check(self, response: str, retrieved: list[RetrievedChunk]) -> GroundingResult:
        context = " ".join(c.text for c in retrieved)
        norm_ctx = normalize(context)
        flagged: list[str] = []

        # 1. numeric claims
        for claim in extract_claims(response):
            if not claim_in_context(claim, context):
                flagged.append(f"number:{claim}")

        # 2. named payment entities
        norm_resp = normalize(response)
        for ent in ENTITIES:
            if ent in norm_resp.split() and ent not in norm_ctx.split():
                flagged.append(f"entity:{ent}")

        method = "regex"
        # 3. optional NLI entailment (real build only)
        if self._nli is not None:
            method = "regex+nli"
            if not self._nli.entails(premise=context, hypothesis=response):
                flagged.append("nli:not-entailed")

        return GroundingResult(passed=not flagged, flagged_claims=flagged, method=method)
