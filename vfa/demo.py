"""Offline demo: drive the orchestrator with text utterances (simulated transport) and
print a readable per-turn trace. Run from repo root:  python3 -m vfa.demo
No keys, no Docker — uses in-memory retrieval + fake STT/LLM/TTS.
"""
from __future__ import annotations

import logging

from .config import load_settings
from .factory import build_auto
from .kb.ingest import load_kb

UTTERANCES = [
    "How much does Razorpay charge per transaction?",                 # expect: early-exit
    "My customer was debited but the payment shows failed, what should I do?",  # expect: semantic/LLM
    "Is Razorpay PCI DSS compliant?",                                 # expect: lexical/early-exit
    "Can I speak to a human agent please?",                           # expect: escalated_explicit
    "flibberty wobble nonsense tokens here",                          # expect: escalated_floor
]


def _print_turn(r) -> None:
    g = r.gate
    print(f"\nCALLER: {r.utterance}")
    print(f"  -> {r.summary()}")
    print(f"     variant={r.active_variant}  gate={g.reason}")
    print(f"     gate.conditions: score={g.conditions.get('lexical_score')} "
          f"> tau({g.conditions.get('tau_bm25')})={g.conditions.get('score_gt_tau')}, "
          f"agree={g.conditions.get('paths_agree')}, faq={g.conditions.get('is_faq')}")
    lt = r.lexical.top
    st = r.semantic.top if r.semantic else None
    print(f"     lexical top:  {lt.chunk_id if lt else None} ({lt.score:.3f})" if lt else "     lexical top:  none")
    print(f"     semantic top: {st.chunk_id if st else None} ({st.score:.3f})" if st else "     semantic top: none")
    if r.grounding:
        gl = r.grounding.get("lexical")
        gs = r.grounding.get("semantic")
        print(f"     grounding: lexical={_g(gl)}  semantic={_g(gs)}")


def _g(gr) -> str:
    if gr is None:
        return "n/a"
    return "PASS" if gr.passed else f"FAIL{gr.flagged_claims}"


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    chunks = load_kb()
    eligible = sum(c.early_exit_eligible for c in chunks)
    print(f"Loaded {len(chunks)} KB chunks ({eligible} voice-eligible for early-exit). "
          f"Offline mode = {settings.offline}. Variant = {settings.ab_variant}.")
    orch, backends = build_auto(settings, chunks)
    print(f"Backends: lexical={backends['lexical']}  semantic={backends['semantic']}")
    print(f"Models:   embedder={backends['embedder']}  reranker={backends['reranker']}")
    print(f"Voice:    llm={backends['llm']}  tts={backends['tts']}")

    call_id = "demo-call-1"
    for i, u in enumerate(UTTERANCES, start=1):
        _print_turn(orch.handle_turn(call_id, i, u))

    print(f"\nShadow log rows written: {orch.shadow.count()}  (db: {settings.shadow_db})")
    orch.shadow.close()


if __name__ == "__main__":
    main()
