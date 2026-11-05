"""Text normalisation, tokenisation, a small Indian-English synonym map, and
claim-extraction helpers for the grounding guard. Pure stdlib."""
from __future__ import annotations

import re
import unicodedata

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
# Grounding verifies that every number the answer states appears in the retrieved context.
# We match on bare digit-runs after normalising formatting, so "2 %" grounds against
# "2 percent", and narrow spaces / non-breaking hyphens the LLM emits don't cause misses.
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalize(text: str) -> str:
    t = text.lower().strip()
    for long, short in SYNONYMS.items():
        t = t.replace(long, short)
    return t


def tokenize(text: str) -> list[str]:
    return _WORD_RE.findall(normalize(text))


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def _norm_ground(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)        # narrow/no-break spaces -> normal
    t = t.replace("%", " percent ")                # "2%" grounds against "2 percent"
    return re.sub(r"[‐-―−]", "-", t)  # unicode dashes -> ascii


def _numbers(text: str) -> list[str]:
    return [m.replace(",", "") for m in _NUM_RE.findall(_norm_ground(text))]


def extract_claims(text: str) -> list[str]:
    """Numeric claims (bare digit-runs) that must trace back to retrieved context."""
    seen, out = set(), []
    for n in _numbers(text):
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def claim_in_context(claim: str, context: str) -> bool:
    return claim in set(_numbers(context))
