import unittest

from vfa.eval.dataset import EvalExample
from vfa.eval.harness import Signals, classify, score

T = dict(tau_bm25=0.62, tau_rerank=0.08, tau_floor=0.18, tau_answerable=0.45)


def sig(**kw):
    base = dict(explicit_human=False, lex_top_id="c1", lex_top_score=0.9, lex_top_type="faq",
                lex_top_eligible=True, lex_second_score=0.2, sem_top_id="c1", sem_top_score=0.9,
                rerank_top_id="c1", rerank_top_score=0.9, starts_qword=True, short=True)
    base.update(kw)
    return Signals(**base)


class TestClassify(unittest.TestCase):
    def test_triple_lock_early_exit(self):
        self.assertEqual(classify(sig(), **T), ("early_exit", "c1"))

    def test_explicit_human_escalates(self):
        self.assertEqual(classify(sig(explicit_human=True), **T)[0], "escalate")

    def test_weak_reranker_escalates(self):
        # not early (disagree), not floor, semantic path, reranker below bar -> escalate
        s = sig(lex_top_id="c1", sem_top_id="c2", lex_top_score=0.3, sem_top_score=0.3,
                rerank_top_id="c2", rerank_top_score=0.01, starts_qword=False, short=False)
        self.assertEqual(classify(s, **T)[0], "escalate")

    def test_confident_semantic_serves(self):
        s = sig(lex_top_id="c1", sem_top_id="c2", lex_top_score=0.3, sem_top_score=0.8,
                rerank_top_id="c2", rerank_top_score=0.9, starts_qword=False, short=False)
        self.assertEqual(classify(s, **T), ("semantic", "c2"))


class TestScore(unittest.TestCase):
    def test_counts_wrong_answers_and_deflection(self):
        exs = [
            EvalExample("good", "c1", "m"),                       # answerable, gold c1
            EvalExample("oodk", None, "ESCALATE"),                 # should escalate
            EvalExample("falseserve", None, "ESCALATE"),           # should escalate (but will serve)
        ]
        sigs = [
            sig(),                                                 # -> early_exit c1 == gold -> correct_serve
            sig(lex_top_score=0.1, sem_top_score=0.1, rerank_top_score=0.0,
                lex_top_id="c9", sem_top_id="c9", rerank_top_id="c9"),  # floor -> escalate -> correct
            sig(lex_top_id="c2", sem_top_id="c2", lex_top_score=0.3, sem_top_score=0.8,
                rerank_top_id="c2", rerank_top_score=0.9, starts_qword=False, short=False),  # serves -> false_serve
        ]
        m = score(exs, sigs, **T)
        self.assertEqual(m.correct_serve, 1)
        self.assertEqual(m.correct_escalate, 1)
        self.assertEqual(m.false_serve, 1)
        self.assertEqual(m.wrong_answers, 1)
        self.assertEqual(m.deflection, 1.0)   # 1 of 1 answerable served correctly


if __name__ == "__main__":
    unittest.main()
