"""Turn Orchestrator — R2, the hub (design §10). Composes the stateless spokes into
one turn: transcribe -> redact -> retrieve BOTH paths -> triple-lock gate -> serve
(early-exit cache OR A/B-selected candidate with grounding) -> escalate on failure ->
TTS -> shadow-log both candidates.

Everything here is pure orchestration; the spokes do the work. The grounding guard runs
ONLY on the semantic (LLM) candidate's serve decision — early-exit turns are authorised by
the triple-lock, never routed through the guard (design boundary fix #1).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from ..ab.switch import ABSwitch
from ..config import Settings
from ..escalation import CallbackTicketWriter
from ..gate import evaluate_gate
from ..grounding.guard import GroundingGuard
from ..llm.base import Synthesizer
from ..prompts import ESCALATION_LINE, HUMAN_REQUEST_WORDS
from ..redact import PIIRedactor
from ..util.text import token_set
from ..rerank.reranker import Reranker
from ..retrieval.base import Retriever
from ..schemas import (GateDecision, GroundingResult, KBChunk, PathResult, ShadowRow,
                       TurnResult, has_card_digits)
from ..shadow.logger import ShadowLogger
from ..smalltalk import classify as classify_smalltalk
from ..stt.base import Transcriber
from ..tts.base import TTS
from ..tts.cache import AudioCache


@dataclass
class Orchestrator:
    settings: Settings
    transcriber: Transcriber
    redactor: PIIRedactor
    lexical: Retriever
    semantic: Retriever
    reranker: Reranker
    synthesizer: Synthesizer
    guard: GroundingGuard
    ab: ABSwitch
    audio_cache: AudioCache
    tts: TTS
    escalation: CallbackTicketWriter
    shadow: ShadowLogger
    chunk_answers: dict[str, str]   # chunk_id -> canonical answer (for cache hash check)

    def handle_turn(self, call_id: str, turn_id: int, audio: str) -> TurnResult:
        t0 = time.perf_counter()
        s = self.settings

        utterance = self.transcriber.transcribe(audio)
        utterance, _pii_hits = self.redactor.redact(utterance)

        # Pre-retrieval conversational layer: greetings / thanks / goodbye / "are you a bot?"
        # get a canned, FACT-FREE reply instead of a KB miss. Runs before the explicit-human
        # check so "are you a human?" (an identity question) is answered, not escalated, while
        # "connect me to a human" (no identity-question form) still falls through to escalate.
        st = classify_smalltalk(utterance)
        if st:
            return self._smalltalk_turn(call_id, turn_id, utterance, st[0], st[1], t0)

        explicit_human = bool(token_set(utterance) & HUMAN_REQUEST_WORDS)   # punctuation-safe

        # --- retrieve both paths (both always run, for the shadow log) ---
        lex = self._retrieve(self.lexical, utterance, s.top_k)
        lex.candidate_response = lex.top.text if lex.top else None

        if self.ab.skip_semantic:
            sem = PathResult(path="semantic")
            reranked = []
        else:
            sem = self._retrieve(self.semantic, utterance, s.top_k)
            reranked = self.reranker.rerank(utterance, sem.retrieved, s.rerank_top_n)
            sem.candidate_response = self.synthesizer.synthesize(utterance, reranked, s.max_answer_words) or None

        # --- grounding on BOTH candidates (for logging); serve decision uses the served one ---
        gr_lex = self.guard.check(lex.candidate_response or "", lex.retrieved[: s.rerank_top_n]) \
            if lex.candidate_response else None
        gr_sem = self.guard.check(sem.candidate_response or "", reranked) \
            if sem.candidate_response else None

        gate = evaluate_gate(lex, sem, s)

        # --- decide outcome / served response (order matters) ---
        filler_played = False
        if explicit_human:
            outcome, served_path, response = "escalated_explicit", "escalation", self._escalate(
                call_id, turn_id, utterance, "caller asked for a human")
        elif self._below_floor(lex, sem):
            outcome, served_path, response = "escalated_floor", "escalation", self._escalate(
                call_id, turn_id, utterance, "both paths below floor")
        elif gate.early_exit:
            outcome, served_path = "early_exit", "lexical (early-exit)"
            response = lex.candidate_response
            self._serve_early_exit_audio(gate.chunk_id, response)
        else:
            served = self.ab.select(utterance, lex, sem)
            # a non-voice-safe chunk (too long, or containing card digits) must never be read
            # verbatim on the lexical arm -> defer to the grounded LLM summary.
            if served == "lexical" and lex.top and not lex.top.early_exit_eligible:
                served = "semantic"
            if served == "semantic":
                # LLM-first answerability: the LLM replies INSUFFICIENT_CONTEXT (-> empty) when
                # the context can't answer, and the grounding guard catches fabricated numbers.
                # No reranker pre-gate, so paraphrases/edge cases get a grounded answer instead
                # of collapsing to a human handoff. (floor check above already caught empty retrieval)
                if gr_sem and gr_sem.passed and sem.candidate_response:
                    outcome, served_path, response = "resolved", "semantic", sem.candidate_response
                    self._live_tts(response)
                else:
                    outcome, served_path, response = "escalated_grounding", "escalation", self._escalate(
                        call_id, turn_id, utterance, "LLM declined (insufficient context) or grounding failed")
            else:  # explicit lexical variant: serve the BM25 answer, gated on its own score
                if lex.top_score < s.tau_answerable:
                    outcome, served_path, response = "escalated_unanswerable", "escalation", self._escalate(
                        call_id, turn_id, utterance, f"lexical support {lex.top_score:.2f} < tau_answerable")
                else:
                    outcome, served_path, response = "resolved", "lexical", (lex.candidate_response or "")
                    self._live_tts(response)

        # hard safety net: never speak card-like digit runs, whatever the path/model produced
        if outcome in ("resolved", "early_exit") and response and has_card_digits(response):
            outcome, served_path, response = "escalated_unanswerable", "escalation", self._escalate(
                call_id, turn_id, utterance, "response contained card-like digits; not read aloud")

        total_ms = (time.perf_counter() - t0) * 1000.0

        result = TurnResult(
            call_id=call_id, turn_id=turn_id, utterance=utterance, served_path=served_path,
            response=response, outcome=outcome, active_variant=self.ab.variant, gate=gate,
            grounding={"lexical": gr_lex, "semantic": gr_sem} if (gr_lex or gr_sem) else {},
            lexical=lex, semantic=(None if self.ab.skip_semantic else sem),
            filler_played=filler_played, total_latency_ms=total_ms,
        )
        self._log(result, gr_lex, gr_sem)
        return result

    # ---- helpers -----------------------------------------------------------
    def _smalltalk_turn(self, call_id: str, turn_id: int, utterance: str,
                        intent: str, reply: str, t0: float) -> TurnResult:
        """Serve a canned conversational reply — no retrieval, no LLM, no KB touched."""
        self._live_tts(reply)
        gate = GateDecision(early_exit=False, reason=f"smalltalk:{intent}")
        result = TurnResult(
            call_id=call_id, turn_id=turn_id, utterance=utterance, served_path="smalltalk",
            response=reply, outcome="smalltalk", active_variant=self.ab.variant, gate=gate,
            grounding={}, lexical=PathResult(path="lexical"), semantic=None,
            total_latency_ms=(time.perf_counter() - t0) * 1000.0,
        )
        self._log(result, None, None)
        return result

    def _retrieve(self, retriever: Retriever, utterance: str, k: int) -> PathResult:
        t = time.perf_counter()
        hits = retriever.search(utterance, k)
        return PathResult(path=retriever.name, retrieved=hits,
                          latency_ms=(time.perf_counter() - t) * 1000.0)

    def _below_floor(self, lex: PathResult, sem: PathResult) -> bool:
        return lex.top_score < self.settings.tau_floor and sem.top_score < self.settings.tau_floor

    def _escalate(self, call_id: str, turn_id: int, utterance: str, reason: str) -> str:
        self.escalation.open(call_id, turn_id, utterance, reason)
        return ESCALATION_LINE

    def _serve_early_exit_audio(self, chunk_id: str | None, answer: str | None) -> None:
        if not chunk_id or answer is None:
            return
        path = self.audio_cache.get(chunk_id, answer)
        if path is None:                      # cache miss / stale -> fail forward to live TTS
            self._live_tts(answer)

    def _live_tts(self, text: str) -> None:
        try:
            self.tts.synthesize(text, f"{self.settings.audio_dir}/_live_turn.audio")
        except Exception:
            pass  # POC: TTS failure must not crash the turn (production: fallback engine)

    def _log(self, r: TurnResult, gr_lex: GroundingResult | None, gr_sem: GroundingResult | None) -> None:
        self.shadow.write(ShadowRow(
            call_id=r.call_id, turn_id=r.turn_id, ts=r.ts,
            active_variant=r.active_variant, served_path=r.served_path,
            utterance_text=r.utterance, outcome=r.outcome,
            gate_early_exit=r.gate.early_exit, gate_reason=r.gate.reason,
            lexical_chunk_ids=[c.chunk_id for c in r.lexical.retrieved],
            lexical_scores=[round(c.score, 4) for c in r.lexical.retrieved],
            lexical_candidate=r.lexical.candidate_response, lexical_latency_ms=r.lexical.latency_ms,
            semantic_chunk_ids=[c.chunk_id for c in r.semantic.retrieved] if r.semantic else [],
            semantic_scores=[round(c.score, 4) for c in r.semantic.retrieved] if r.semantic else [],
            semantic_candidate=r.semantic.candidate_response if r.semantic else None,
            semantic_latency_ms=r.semantic.latency_ms if r.semantic else 0.0,
            grounding_lexical_passed=(gr_lex.passed if gr_lex else None),
            grounding_semantic_passed=(gr_sem.passed if gr_sem else None),
            total_latency_ms=r.total_latency_ms, filler_played=r.filler_played,
        ))
