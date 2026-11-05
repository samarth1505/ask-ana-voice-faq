"""Eval harness + threshold tuner (design §9 eval harness).

Strategy: capture each turn's retrieval/rerank SIGNALS once (the expensive step), then
sweep thresholds analytically over those signals — no model re-inference per threshold.

Reliability-first objective: choose thresholds that minimise WRONG ANSWERS first
(serving when we should escalate, or serving the wrong chunk), then maximise deflection.

Run:  VFA_REAL_MODELS=1 ./.venv312/bin/python -m vfa.eval.harness
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings, load_settings
from ..factory import build_auto
from ..kb.ingest import load_kb
from ..prompts import HUMAN_REQUEST_WORDS
from ..util.text import token_set
from .dataset import EvalExample, load_evalset

_QWORDS = {"what", "when", "where", "which", "how", "who", "is", "are", "do", "does", "can"}


@dataclass
class Signals:
    explicit_human: bool
    lex_top_id: str | None
    lex_top_score: float
    lex_top_type: str
    lex_top_eligible: bool
    lex_second_score: float
    sem_top_id: str | None
    sem_top_score: float
    rerank_top_id: str | None
    rerank_top_score: float
    starts_qword: bool
    short: bool


@dataclass
class Metrics:
    tau_bm25: float
    tau_rerank: float
    correct_serve: int = 0
    correct_escalate: int = 0
    false_serve: int = 0      # gold=escalate but we served  -> WRONG ANSWER
    wrong_chunk: int = 0      # gold=chunk but served a different chunk -> WRONG ANSWER
    missed: int = 0           # gold=chunk but we escalated -> lost deflection
    n_answerable: int = 0
    n_escalate: int = 0

    @property
    def wrong_answers(self) -> int:
        return self.false_serve + self.wrong_chunk

    @property
    def deflection(self) -> float:
        return self.correct_serve / self.n_answerable if self.n_answerable else 0.0

    @property
    def objective(self) -> tuple[int, int]:
        # minimise wrong answers, then maximise correct serves
        return (self.wrong_answers, -self.correct_serve)


def capture(orch, utterance: str, k: int, rerank_top_n: int) -> Signals:
    lex = orch.lexical.search(utterance, k)
    sem = orch.semantic.search(utterance, k)
    reranked = orch.reranker.rerank(utterance, sem, rerank_top_n) if sem else []
    words = utterance.strip().lower().split()
    return Signals(
        explicit_human=bool(token_set(utterance) & HUMAN_REQUEST_WORDS),
        lex_top_id=(lex[0].chunk_id if lex else None),
        lex_top_score=(lex[0].score if lex else 0.0),
        lex_top_type=(lex[0].type if lex else "faq"),
        lex_top_eligible=(lex[0].early_exit_eligible if lex else False),
        lex_second_score=(lex[1].score if len(lex) > 1 else 0.0),
        sem_top_id=(sem[0].chunk_id if sem else None),
        sem_top_score=(sem[0].score if sem else 0.0),
        rerank_top_id=(reranked[0].chunk_id if reranked else None),
        rerank_top_score=(reranked[0].score if reranked else 0.0),
        starts_qword=bool(words) and words[0] in _QWORDS,
        short=len(words) <= 6,
    )


def classify(s: Signals, tau_bm25: float, tau_rerank: float,
             tau_floor: float, tau_answerable: float) -> tuple[str, str | None]:
    """Replicates the orchestrator's serve decision. Returns (action, served_chunk_id)."""
    if s.explicit_human:
        return "escalate", None
    # triple-lock early exit
    if (s.lex_top_score > tau_bm25 and s.lex_top_id == s.sem_top_id
            and s.lex_top_type == "faq" and s.lex_top_eligible):
        return "early_exit", s.lex_top_id
    # floor
    if s.lex_top_score < tau_floor and s.sem_top_score < tau_floor:
        return "escalate", None
    # A/B auto router (threshold-dependent via tau_bm25)
    margin = s.lex_top_score - s.lex_second_score
    served_lexical = (s.lex_top_score >= tau_bm25 and margin >= 0.10
                      and (s.short or s.starts_qword))
    if served_lexical:
        if s.lex_top_score < tau_answerable:
            return "escalate", None
        return "lexical", s.lex_top_id
    # semantic path: answerability keyed on the reranker
    if s.rerank_top_score < tau_rerank:
        return "escalate", None
    return "semantic", s.rerank_top_id


def score(examples: list[EvalExample], sigs: list[Signals], tau_bm25: float, tau_rerank: float,
          tau_floor: float, tau_answerable: float) -> Metrics:
    m = Metrics(tau_bm25=tau_bm25, tau_rerank=tau_rerank)
    for ex, s in zip(examples, sigs):
        action, served = classify(s, tau_bm25, tau_rerank, tau_floor, tau_answerable)
        escalated = action == "escalate"
        if ex.should_escalate:
            m.n_escalate += 1
            if escalated:
                m.correct_escalate += 1
            else:
                m.false_serve += 1
        else:
            m.n_answerable += 1
            if escalated:
                m.missed += 1
            elif served == ex.gold_chunk_id:
                m.correct_serve += 1
            else:
                m.wrong_chunk += 1
    return m


def sweep(examples, sigs, settings: Settings,
          bm25_grid=None, rerank_grid=None) -> list[Metrics]:
    bm25_grid = bm25_grid or [round(x / 100, 2) for x in range(40, 85, 5)]
    rerank_grid = rerank_grid or [0.02, 0.05, 0.08, 0.12, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    results = [score(examples, sigs, b, r, settings.tau_floor, settings.tau_answerable)
               for b in bm25_grid for r in rerank_grid]
    results.sort(key=lambda m: m.objective)
    return results


def main() -> None:
    settings = load_settings()
    chunks = load_kb()
    orch, backends = build_auto(settings, chunks)
    examples = load_evalset(chunks)
    sigs = [capture(orch, ex.utterance, settings.top_k, settings.rerank_top_n) for ex in examples]

    n_ans = sum(not e.should_escalate for e in examples)
    print(f"Eval set: {len(examples)} examples ({n_ans} answerable, {len(examples) - n_ans} escalate)")
    print(f"Models: embedder={backends['embedder']}  reranker={backends['reranker']}")

    cur = score(examples, sigs, settings.tau_bm25, settings.tau_rerank,
                settings.tau_floor, settings.tau_answerable)
    print(f"\nCURRENT  tau_bm25={settings.tau_bm25} tau_rerank={settings.tau_rerank}: "
          f"wrong={cur.wrong_answers} (false_serve={cur.false_serve} wrong_chunk={cur.wrong_chunk}) "
          f"correct_serve={cur.correct_serve}/{n_ans} missed={cur.missed} "
          f"escalate_ok={cur.correct_escalate}/{cur.n_escalate} deflection={cur.deflection:.0%}")

    results = sweep(examples, sigs, settings)
    print("\nTOP CANDIDATES (minimise wrong answers, then maximise correct serves):")
    print(f"{'bm25':>5} {'rerank':>7} {'wrong':>6} {'false':>6} {'wrongC':>7} "
          f"{'correct':>8} {'missed':>7} {'escOK':>6} {'defl':>6}")
    for m in results[:8]:
        print(f"{m.tau_bm25:>5} {m.tau_rerank:>7} {m.wrong_answers:>6} {m.false_serve:>6} "
              f"{m.wrong_chunk:>7} {m.correct_serve:>8} {m.missed:>7} "
              f"{m.correct_escalate:>6} {m.deflection:>5.0%}")

    best = results[0]
    print("\nMisclassified at recommended thresholds (none are false-serves = no wrong answer to out-of-KB):")
    any_bad = False
    for ex, s in zip(examples, sigs):
        action, served = classify(s, best.tau_bm25, best.tau_rerank,
                                  settings.tau_floor, settings.tau_answerable)
        esc = action == "escalate"
        tag = None
        if ex.should_escalate and not esc:
            tag = "FALSE_SERVE"
        elif not ex.should_escalate and esc:
            tag = "MISSED"
        elif not ex.should_escalate and served != ex.gold_chunk_id:
            tag = "WRONG_CHUNK"
        if tag:
            any_bad = True
            print(f"  [{tag:11}] {ex.utterance!r}  gold={ex.marker}  "
                  f"rerank={s.rerank_top_score:.2f} lex={s.lex_top_score:.2f}")
    if not any_bad:
        print("  (none)")

    out = {"tau_bm25": best.tau_bm25, "tau_rerank": best.tau_rerank,
           "wrong_answers": best.wrong_answers, "deflection": round(best.deflection, 3),
           "models": backends}
    Path("eval").mkdir(exist_ok=True)
    Path("eval/tuned_thresholds.json").write_text(json.dumps(out, indent=2))
    print(f"\nRECOMMENDED  tau_bm25={best.tau_bm25}  tau_rerank={best.tau_rerank}  "
          f"(wrong_answers={best.wrong_answers}, deflection={best.deflection:.0%})")
    print("Written to eval/tuned_thresholds.json")


if __name__ == "__main__":
    main()
