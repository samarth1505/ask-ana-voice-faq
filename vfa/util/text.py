"""Text normalisation, tokenisation, a small Indian-English synonym map, and
claim-extraction helpers for the grounding guard. Pure stdlib."""
from __future__ import annotations

import re

# design §8 step 3: synonym dictionary for the Indian-English analyzer.
SYNONYMS: dict[str, str] = {
    "unified payments interface": "upi",
    "national electronic funds transfer": "neft",
    "real time gross settlement": "rtgs",
    "immediate payment service": "imps",
    "charges": "fees",
    "charge": "fee",
    "reversal": "refund",
    "reversed": "refund",
}

_WORD_RE = re.compile(r"[a-z0-9]+")
# Numbers, money, percentages, day/business-day durations — the claims a grounding
# guard must verify against retrieved context (design §6/§11).
_CLAIM_RE = re.compile(
    r"(?:₹\s?\d[\d,]*(?:\.\d+)?)"          # ₹1,200
    r"|(?:\d+(?:\.\d+)?\s?%)"               # 2%
    r"|(?:\d+\s*[-–]\s*\d+)"                # 5-7
    r"|(?:\b\d[\d,]*(?:\.\d+)?\b)",         # plain numbers
)


def normalize(text: str) -> str:
    t = text.lower().strip()
    for long, short in SYNONYMS.items():
        t = t.replace(long, short)
    return t


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(normalize(text))


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def extract_claims(text: str) -> list[str]:
    """Numeric/quantitative claims that must trace back to retrieved context."""
    claims = []
    for m in _CLAIM_RE.findall(text):
        c = m.strip()
        if c:
            claims.append(_canon_number(c))
    # de-dupe, keep order
    seen, out = set(), []
    for c in claims:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _canon_number(s: str) -> str:
    return s.replace(" ", "").replace(",", "").replace("–", "-")


def claim_in_context(claim: str, context: str) -> bool:
    """Does a numeric claim appear in the retrieved context (digits-only match)?"""
    ctx_numbers = {_canon_number(x) for x in _CLAIM_RE.findall(context)}
    return _canon_number(claim) in ctx_numbers
