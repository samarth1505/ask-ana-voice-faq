"""Triple-lock early-exit gate (design §5/§10, R10).

Early exit (skip the LLM, serve pre-synth audio) is allowed ONLY when all three hold:
  1. lexical top score > tau_bm25
  2. lexical top chunk == semantic top chunk   (dual-path agreement)
  3. that chunk is type == "faq"                (question field => match is semantic by design)

Any miss -> fall through to the LLM + grounding path. A high BM25 score alone is NOT
enough (that was the original single-lock bug that could serve a confident wrong answer).
"""
from __future__ import annotations

from .config import Settings
from .schemas import GateDecision, PathResult


def evaluate_gate(lexical: PathResult, semantic: PathResult, settings: Settings) -> GateDecision:
    lex_top = lexical.top
    sem_top = semantic.top

    cond_score = bool(lex_top) and lex_top.score > settings.tau_bm25
    cond_agree = bool(lex_top and sem_top) and lex_top.chunk_id == sem_top.chunk_id
    cond_faq = bool(lex_top) and lex_top.type == "faq"
    # voice-safety: don't serve a long/card-number answer verbatim on early-exit
    cond_eligible = bool(lex_top) and lex_top.early_exit_eligible

    conditions = {
        "score_gt_tau": cond_score,
        "lexical_score": round(lex_top.score, 4) if lex_top else 0.0,
        "tau_bm25": settings.tau_bm25,
        "paths_agree": cond_agree,
        "lexical_top": lex_top.chunk_id if lex_top else None,
        "semantic_top": sem_top.chunk_id if sem_top else None,
        "is_faq": cond_faq,
        "voice_eligible": cond_eligible,
    }

    early = cond_score and cond_agree and cond_faq and cond_eligible
    if early:
        reason = "triple-lock satisfied"
    else:
        misses = [n for n, ok in
                  (("score>tau", cond_score), ("paths-agree", cond_agree),
                   ("is-faq", cond_faq), ("voice-eligible", cond_eligible))
                  if not ok]
        reason = "fall-through: " + ", ".join(misses)

    return GateDecision(
        early_exit=early,
        reason=reason,
        chunk_id=(lex_top.chunk_id if early and lex_top else None),
        conditions=conditions,
    )
