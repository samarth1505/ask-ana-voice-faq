"""Real ElevenLabs TTS (stdlib urllib). Writes MP3 bytes to out_path. Implements the same
interface as FakeTTS. Each call SPENDS credits — gated behind VFA_REAL_TTS in the factory. (R16)
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path


class ElevenLabsTTS:
    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_turbo_v2_5",
                 timeout_ms: int = 20000) -> None:
        self._key = api_key
        self._voice = voice_id
        self._model = model_id
        self._timeout = timeout_ms / 1000.0

    def synthesize_bytes(self, text: str) -> bytes:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice}"
        body = json.dumps({"text": text, "model_id": self._model}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST", headers={
            "xi-api-key": self._key, "Content-Type": "application/json", "Accept": "audio/mpeg",
        })
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            return r.read()

    def synthesize(self, text: str, out_path: str) -> str:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(self.synthesize_bytes(text))
        return str(p)
