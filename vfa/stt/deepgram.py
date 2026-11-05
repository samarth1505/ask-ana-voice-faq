"""Real Deepgram STT (stdlib urllib), prerecorded endpoint. `transcribe(audio_path)` posts
the audio bytes and returns the final transcript. Used by the (future) telephony transport;
the text-driven POC demo keeps FakeTranscriber since there's no audio in simulation. (R4)
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path


class DeepgramTranscriber:
    def __init__(self, api_key: str, model: str = "nova-2", content_type: str = "audio/mpeg",
                 timeout_ms: int = 30000) -> None:
        self._key = api_key
        self._model = model
        self._ct = content_type
        self._timeout = timeout_ms / 1000.0

    def _post(self, data: bytes, content_type: str) -> str:
        url = f"https://api.deepgram.com/v1/listen?model={self._model}&smart_format=true"
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"Token {self._key}", "Content-Type": content_type,
        })
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            j = json.loads(r.read())
        return j["results"]["channels"][0]["alternatives"][0]["transcript"].strip()

    def transcribe(self, audio: str) -> str:
        return self._post(Path(audio).read_bytes(), self._ct)

    def transcribe_bytes(self, data: bytes, content_type: str | None = None) -> str:
        return self._post(data, content_type or self._ct)
