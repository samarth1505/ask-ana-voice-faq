"""TTS interface + offline fake. The fake "synthesizes" by writing the text to a file
in the audio dir and returning its path — enough to exercise the cache + serving path
without a real engine. ElevenLabs adapter implements the same interface. (R16/D10)
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ..schemas import chunk_id_for


class TTS(Protocol):
    def synthesize(self, text: str, out_path: str) -> str: ...


class FakeTTS:
    """Writes `[[TTS]] <text>` to out_path; returns the path. No audio bytes needed."""

    def synthesize(self, text: str, out_path: str) -> str:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"[[TTS fake]] {text}", encoding="utf-8")
        return str(p)

    @staticmethod
    def phrase_id(text: str) -> str:
        return chunk_id_for(text)
