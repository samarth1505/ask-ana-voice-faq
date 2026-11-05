"""PII redactor (design §11/R5): scrub card/OTP/Aadhaar-like digit sequences from the
transcript BEFORE retrieval, logging, or anything downstream.

⚠️ Honest scope (flagged): with a cloud STT the raw audio already reached the vendor
before this runs — this protects OUR downstream systems/logs, not the vendor hop. The
vendor no-retention commitment covers that. (design §11 'PII' note)
"""
from __future__ import annotations

import re

# 12/13/16-digit card/Aadhaar sequences (allowing spaces/dashes), and 4/6-digit OTPs.
_CARD = re.compile(r"\b(?:\d[ -]?){12,16}\b")
_OTP = re.compile(r"\b\d{4}\b|\b\d{6}\b")


class PIIRedactor:
    def redact(self, text: str) -> tuple[str, int]:
        hits = 0
        def _sub_card(m: re.Match) -> str:
            nonlocal hits
            digits = re.sub(r"\D", "", m.group())
            if 12 <= len(digits) <= 16:
                hits += 1
                return "[REDACTED_NUMBER]"
            return m.group()
        text = _CARD.sub(_sub_card, text)
        def _sub_otp(m: re.Match) -> str:
            nonlocal hits
            hits += 1
            return "[REDACTED_OTP]"
        text = _OTP.sub(_sub_otp, text)
        return text, hits
