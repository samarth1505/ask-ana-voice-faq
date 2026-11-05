"""STT interface + offline fake. In POC simulation the 'audio' is just text, so the
fake is identity. Real Deepgram streaming adapter implements the same interface. (R4)
"""
from __future__ import annotations

from typing import Protocol


class Transcriber(Protocol):
    def transcribe(self, audio: str) -> str: ...


class FakeTranscriber:
    """Identity transcriber for simulated (text-driven) turns."""

    def transcribe(self, audio: str) -> str:
        return audio.strip()
