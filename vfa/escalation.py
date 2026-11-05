"""Callback + ticket writer (design §6/A22). POC = append a JSON line to a local log
and return a ticket id (Freshdesk + real Exotel outbound dialing are deferred). The
ticket references the transcript by pointer, never inline. (design A22/A25)
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path


class CallbackTicketWriter:
    def __init__(self, log_path: str = "./data/tickets.log") -> None:
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def open(self, call_id: str, turn_id: int, utterance: str, reason: str,
             transcript_ref: str | None = None) -> str:
        ticket_id = f"TCK-{uuid.uuid4().hex[:8]}"
        record = {
            "ticket_id": ticket_id,
            "ts": time.time(),
            "call_id": call_id,
            "turn_id": turn_id,
            "reason": reason,
            "utterance": utterance,
            "transcript_ref": transcript_ref,
            "sla_callback_minutes": 5,
            "status": "queued",   # production: enqueue outbound Exotel dial
        }
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return ticket_id
