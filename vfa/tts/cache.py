"""Pre-synth audio cache (design §5/§8/R11, A21). Maps chunk_id -> audio file on disk
(local-disk stands in for Cloudflare R2 in the POC). Stores an audio_hash alongside so a
stale/mismatched entry fails forward to live TTS instead of playing stale audio.
"""
from __future__ import annotations

import json
from pathlib import Path

from .base import TTS
from ..schemas import chunk_id_for


class AudioCache:
    def __init__(self, audio_dir: str, tts: TTS) -> None:
        self._dir = Path(audio_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._tts = tts
        self._index_path = self._dir / "index.json"
        self._index: dict[str, str] = self._load_index()

    def _load_index(self) -> dict[str, str]:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_index(self) -> None:
        self._index_path.write_text(json.dumps(self._index, indent=2))

    def _path(self, chunk_id: str) -> Path:
        return self._dir / f"{chunk_id}.audio"

    def presynthesize(self, chunk_id: str, answer: str) -> None:
        """At ingest: synth once, record the audio_hash of the source answer."""
        self._tts.synthesize(answer, str(self._path(chunk_id)))
        self._index[chunk_id] = chunk_id_for(answer)
        self._save_index()

    def get(self, chunk_id: str, expected_answer: str) -> str | None:
        """Return the cached audio path IFF present and the hash matches; else None
        (caller fails forward to live TTS — never a stale play)."""
        p = self._path(chunk_id)
        if not p.exists():
            return None
        if self._index.get(chunk_id) != chunk_id_for(expected_answer):
            return None  # stale: source answer changed since pre-synth
        return str(p)
