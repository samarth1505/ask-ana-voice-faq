"""Interactive chat with the agent — type a question, get Ana's answer.

Run (text only):        python3 -m vfa.chat
Real retrieval+models:  VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.chat
Hear it speak (macOS):  VFA_SPEAK=1 VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.chat
                        (VFA_SPEAK synthesizes each answer via ElevenLabs and plays it —
                         this spends credits; off by default.)

Type your question at the `you>` prompt. Commands: `quit` / `exit` to leave.
"""
from __future__ import annotations

import os
import subprocess
import time

from .config import load_settings
from .factory import build_auto
from .kb.ingest import load_kb
from .prompts import GREETING

_OUTCOME_HINT = {
    "early_exit": "cache hit (no LLM)",
    "resolved": "answered",
    "escalated_grounding": "escalated — answer failed grounding",
    "escalated_floor": "escalated — nothing matched",
    "escalated_unanswerable": "escalated — not confident enough",
    "escalated_explicit": "escalated — you asked for a human",
}


def _speak(settings, text: str, turn: int) -> None:
    """Synthesize one answer via ElevenLabs and play it (macOS afplay). Spends credits."""
    if not (settings.elevenlabs_api_key and settings.elevenlabs_voice_id and text):
        return
    try:
        from .tts.elevenlabs import ElevenLabsTTS
        path = os.path.join(settings.audio_dir, f"chat_turn_{turn}.mp3")
        ElevenLabsTTS(settings.elevenlabs_api_key, settings.elevenlabs_voice_id,
                      settings.elevenlabs_model_id).synthesize(text, path)
        subprocess.run(["afplay", path], check=False)
    except Exception as e:
        print(f"   (voice playback unavailable: {e})")


def main() -> None:
    settings = load_settings()
    speak = (os.environ.get("VFA_SPEAK", "") or "").lower() in ("1", "true", "yes")
    chunks = load_kb()
    orch, backends = build_auto(settings, chunks)

    print("─" * 70)
    print(f"Voice FAQ Agent — interactive chat   (speak={'on' if speak else 'off'})")
    print(f"retrieval: {backends['lexical']} / {backends['semantic']}")
    print(f"llm: {backends['llm']}   tts: {backends['tts']}   embedder: {backends['embedder']}")
    print("─" * 70)
    print(f"\nAna> {GREETING}")
    if speak:
        _speak(settings, GREETING, 0)

    call_id = f"chat-{int(time.time())}"
    turn = 0
    while True:
        try:
            u = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[bye]")
            break
        if not u:
            continue
        if u.lower() in ("quit", "exit", ":q"):
            print("[bye]")
            break
        turn += 1
        r = orch.handle_turn(call_id, turn, u)
        print(f"\nAna> {r.response}")
        hint = _OUTCOME_HINT.get(r.outcome, r.outcome)
        print(f"       · {hint} · path={r.served_path} · {r.total_latency_ms:.0f} ms")
        if speak:
            _speak(settings, r.response or "", turn)

    orch.shadow.close()


if __name__ == "__main__":
    main()
